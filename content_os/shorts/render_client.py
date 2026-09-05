from __future__ import annotations

import asyncio
from urllib.parse import urljoin

import aiohttp


class ShortRenderClient:
    """Thin client for the persistent Shorts Worker v2 contract.

    It intentionally does not know how scripts are generated or reviewed. Its only
    job is submit → poll → download, so production stages remain replaceable.
    """

    def __init__(self, settings):
        self.settings = settings

    @property
    def ready(self) -> bool:
        return bool(self.settings.mpt_base_url)

    @property
    def headers(self) -> dict[str, str]:
        return {"x-api-key": self.settings.mpt_api_key} if self.settings.mpt_api_key else {}

    async def probe(self) -> tuple[bool, str]:
        if not self.ready:
            return False, "URL не задан"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12), headers=self.headers) as session:
                async with session.get(self.settings.mpt_base_url + "/health") as response:
                    data = await response.json(content_type=None)
                    if response.status >= 400 or not data.get("ok"):
                        return False, f"HTTP {response.status}"
            providers = data.get("tts") or {}
            voice = ", ".join(key for key, ok in providers.items() if ok) or data.get("voice", "—")
            assets = ",".join(data.get("asset_types") or []) or "stock_video"
            return True, f"Pexels {'да' if data.get('pexels') else 'НЕТ'} · TTS {voice} · assets {assets}"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {str(exc)[:120]}"

    async def render(self, payload: dict, progress=None) -> tuple[str, bytes, str, str]:
        if not self.ready:
            raise RuntimeError("Shorts Worker ещё не подключён")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90), headers=self.headers) as session:
            created = await self._request_json(session, "POST", "/api/v1/videos", json=payload)
            task_id = str(self._data(created).get("task_id", "")).strip()
            if not task_id:
                raise RuntimeError("Shorts Worker не вернул task_id")
            deadline = asyncio.get_running_loop().time() + self.settings.mpt_timeout_minutes * 60
            last_progress = -1
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(8)
                status = self._data(await self._request_json(session, "GET", f"/api/v1/tasks/{task_id}"))
                current = int(status.get("progress", 0) or 0)
                if progress and current != last_progress:
                    await progress(current)
                    last_progress = current
                state = int(status.get("state", 0) or 0)
                if state < 0:
                    raise RuntimeError(str(status.get("error") or "рендер завершился с ошибкой")[:500])
                output = status.get("videos") or []
                if state == 1 and output:
                    video_url = urljoin(self.settings.mpt_base_url + "/", str(output[0]).lstrip("/"))
                    async with session.get(video_url) as response:
                        if response.status >= 400:
                            raise RuntimeError(f"скачивание MP4: HTTP {response.status}")
                        content = await response.read()
                    if len(content) > 49 * 1024 * 1024:
                        raise RuntimeError("готовое видео больше лимита Telegram 49 МБ")
                    warnings = [
                        str(status.get("voice_error") or "").strip(),
                        str(status.get("render_warning") or "").strip(),
                    ]
                    warning = " · ".join(item for item in warnings if item)[:420]
                    return (
                        task_id,
                        content,
                        str(status.get("voice_provider") or "unknown"),
                        warning,
                    )
            raise RuntimeError(f"рендер не завершился за {self.settings.mpt_timeout_minutes} минут")

    async def _request_json(self, session, method: str, path: str, **kwargs):
        async with session.request(method, self.settings.mpt_base_url + path, **kwargs) as response:
            body = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"Shorts Worker HTTP {response.status}: {body[:240]}")
            return __import__("json").loads(body)

    @staticmethod
    def _data(response):
        return response.get("data", response) if isinstance(response, dict) else {}
