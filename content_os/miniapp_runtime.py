from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web


ASSETS = Path(__file__).with_name("miniapp")


def validate_init_data(value: str, bot_token: str, max_age: int = 86400) -> dict:
    """Validate Telegram WebApp initData without trusting browser-supplied identity."""
    pairs = dict(parse_qsl(value or "", keep_blank_values=True))
    supplied = pairs.pop("hash", "")
    if not supplied:
        raise ValueError("Telegram signature is missing")
    data_check = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise ValueError("Telegram signature is invalid")
    auth_date = int(pairs.get("auth_date", "0") or 0)
    if not auth_date or abs(int(time.time()) - auth_date) > max_age:
        raise ValueError("Telegram session has expired")
    try:
        return json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("Telegram user is invalid") from exc


def _row(row) -> dict:
    return dict(row) if row is not None else {}


def dashboard_snapshot(db) -> dict:
    drafts = [_row(item) for channel in ("gifts", "liga") for item in db.recent_drafts(channel, 15)]
    scheduled = [_row(item) for item in db.future_scheduled(datetime.now(db.timezone).isoformat(), 30)]
    analytics = [_row(item) for item in db.analytics_summary(12)]
    players = [_row(item) for item in db.players()[:12]]
    orders = [_row(item) for item in db.service_orders("new", 20)] if hasattr(db, "service_orders") else []
    market = [_row(item) for item in db.radar_posts("gifts", 8)]
    knowledge = [_row(item) for item in db.course_stats(8)] if hasattr(db, "course_stats") else []
    return {
        "generated_at": datetime.now(db.timezone).isoformat(),
        "counts": {
            "review": sum(item.get("status") == "review" for item in drafts),
            "scheduled": len(scheduled),
            "published": sum(item.get("status") == "published" for item in drafts),
            "orders": len(orders),
        },
        "drafts": drafts[:20], "calendar": scheduled, "analytics": analytics,
        "players": players, "orders": orders, "market": market, "knowledge": knowledge,
    }


class MiniAppRuntime:
    def __init__(self, legacy):
        self.legacy = legacy
        self.app = web.Application(middlewares=[self.auth])
        self.app.add_routes([
            web.get("/", self.index), web.get("/app.css", self.css), web.get("/app.js", self.js),
            web.get("/api/dashboard", self.dashboard),
            web.post(r"/api/drafts/{draft_id:\d+}/approve", self.approve),
            web.post(r"/api/drafts/{draft_id:\d+}/publish", self.publish),
            web.post(r"/api/drafts/{draft_id:\d+}/schedule", self.schedule),
            web.post(r"/api/drafts/{draft_id:\d+}/delete", self.delete),
            web.get("/health", self.health),
        ])
        self.runner = None

    @web.middleware
    async def auth(self, request, handler):
        if not request.path.startswith("/api/"):
            return await handler(request)
        try:
            user = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""), self.legacy.settings.bot_token)
        except ValueError as exc:
            raise web.HTTPUnauthorized(text=str(exc)) from exc
        username = str(user.get("username") or "").lower()
        if username not in self.legacy.settings.admins:
            raise web.HTTPForbidden(text="Admin access required")
        request["telegram_user"] = user
        return await handler(request)

    async def index(self, request):
        return web.FileResponse(ASSETS / "index.html")

    async def css(self, request):
        return web.FileResponse(ASSETS / "app.css")

    async def js(self, request):
        return web.FileResponse(ASSETS / "app.js")

    async def health(self, request):
        return web.json_response({"ok": True, "service": "content-os-miniapp"})

    async def dashboard(self, request):
        return web.json_response(dashboard_snapshot(self.legacy.db))

    async def approve(self, request):
        draft_id = int(request.match_info["draft_id"])
        if not self.legacy.db.draft(draft_id):
            raise web.HTTPNotFound(text="Draft not found")
        self.legacy.db.update(draft_id, status="approved")
        return web.json_response({"ok": True, "draft_id": draft_id, "status": "approved"})

    async def delete(self, request):
        draft_id = int(request.match_info["draft_id"])
        if not self.legacy.db.draft(draft_id):
            raise web.HTTPNotFound(text="Draft not found")
        self.legacy.db.update(draft_id, status="deleted")
        return web.json_response({"ok": True, "draft_id": draft_id, "status": "deleted"})

    async def publish(self, request):
        draft_id = int(request.match_info["draft_id"])
        draft = self.legacy.db.draft(draft_id)
        if not draft:
            raise web.HTTPNotFound(text="Draft not found")
        if draft["status"] not in {"approved", "scheduled"}:
            raise web.HTTPConflict(text="Сначала одобри материал")
        mode, warning = await self.legacy.publish(draft_id)
        return web.json_response({"ok": True, "draft_id": draft_id, "status": "published", "mode": mode, "warning": warning})

    async def schedule(self, request):
        draft_id = int(request.match_info["draft_id"])
        draft = self.legacy.db.draft(draft_id)
        if not draft:
            raise web.HTTPNotFound(text="Draft not found")
        if draft["status"] != "approved":
            raise web.HTTPConflict(text="Сначала одобри материал")
        body = await request.json()
        try:
            scheduled = datetime.fromisoformat(str(body.get("scheduled_at") or ""))
        except ValueError as exc:
            raise web.HTTPBadRequest(text="Некорректное время") from exc
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=self.legacy.settings.timezone)
        if scheduled <= datetime.now(self.legacy.settings.timezone):
            raise web.HTTPBadRequest(text="Время должно быть в будущем")
        self.legacy.db.update(draft_id, status="scheduled", scheduled_at=scheduled.isoformat())
        return web.json_response({"ok": True, "draft_id": draft_id, "status": "scheduled", "scheduled_at": scheduled.isoformat()})

    async def start(self, port: int):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        await web.TCPSite(self.runner, "0.0.0.0", port).start()

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()


def install(legacy):
    return MiniAppRuntime(legacy)
