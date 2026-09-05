from __future__ import annotations

import base64
import json
from dataclasses import asdict

from ..visual_renderer import render_card
from .models import ShortBrief
from .presets import DELIVERY_PRESETS, VOICE_PRESETS, voice
from .render_client import ShortRenderClient
from .scenes import ShortSceneService
from .script import ShortScriptService
from .session import ShortSessionStore


SUBTITLE_PRESETS = {"punch", "clean", "sport", "meme"}


class ShortsStudio:
    """Coordinates review-first Shorts production without coupling Telegram UI to render internals."""

    def __init__(self, settings, editor, database):
        self.db = database
        self.scripts = ShortScriptService(editor)
        self.scenes = ShortSceneService(editor)
        self.sessions = ShortSessionStore(database)
        self.renderer = ShortRenderClient(settings)

    async def start(self, draft, delivery_key: str = "punchy") -> tuple[int | str, ShortBrief]:
        normalized = delivery_key if delivery_key in DELIVERY_PRESETS else "punchy"
        brief = await self.scripts.prepare(draft, normalized)
        payload = self.worker_payload(brief)
        # Reuse the existing video-job table so migration does not require a new schema.
        job_id = self.db.save_video_job(draft["id"], json.dumps(payload, ensure_ascii=False, indent=2))
        self.sessions.save(job_id, brief)
        return job_id, brief

    async def rewrite(self, job_id: int | str, mode: str) -> ShortBrief:
        current = self._required(job_id)
        updated = await self.scripts.rewrite(current, mode)
        return self.sessions.replace_script(job_id, updated)

    async def restyle(self, job_id: int | str, preset_key: str) -> ShortBrief:
        normalized = preset_key if preset_key in DELIVERY_PRESETS else "punchy"
        current = self.sessions.choose_style(job_id, normalized)
        if current.draft_id is None:
            raise RuntimeError("У Shorts потеряна связь с исходным постом")
        draft = self.db.draft(int(current.draft_id))
        if not draft:
            raise RuntimeError("Исходный пост больше не найден")
        updated = await self.scripts.prepare(draft, normalized)
        return self.sessions.replace_script(job_id, updated)

    async def remix_scenes(self, job_id: int | str) -> ShortBrief:
        current = self._required(job_id)
        scenes = await self.scenes.remix(current)
        return self.sessions.replace_scenes(job_id, scenes)

    def choose_voice(self, job_id: int | str, preset_key: str) -> ShortBrief:
        normalized = preset_key if preset_key in VOICE_PRESETS else "auto_ru"
        return self.sessions.choose_voice(job_id, normalized)

    def choose_subtitle(self, job_id: int | str, preset_key: str) -> ShortBrief:
        normalized = preset_key if preset_key in SUBTITLE_PRESETS else "punch"
        return self.sessions.choose_subtitle(job_id, normalized)

    async def upload_voice(self, job_id: int | str, content: bytes, filename: str) -> ShortBrief:
        asset_ref = await self.renderer.upload_audio(content, filename)
        brief = self.sessions.choose_voice(job_id, "uploaded")
        brief.metadata["voice_asset_ref"] = asset_ref
        self.sessions.save(job_id, brief)
        return brief

    def approve(self, job_id: int | str) -> ShortBrief:
        return self.sessions.approve(job_id)

    async def render(self, job_id: int | str, progress=None):
        brief = self._required(job_id)
        if not brief.approved:
            raise RuntimeError("Сначала подтверди сценарий")
        return await self.renderer.render(self.worker_payload(brief, studio_job_id=job_id), progress)

    def _scene_payloads(self, brief: ShortBrief) -> list[dict]:
        scenes = [asdict(scene) for scene in brief.scenes]
        if brief.draft_id is None or not any(scene.get("asset_type") == "brand_card" and not scene.get("asset_ref") for scene in scenes):
            return scenes
        draft = self.db.draft(int(brief.draft_id))
        if not draft:
            return scenes
        try:
            card = render_card(brief.channel, draft["text"], draft["format_key"], 0)
            # Inline data asset keeps editor/worker services decoupled from shared disk
            # or public object storage. Worker enforces a strict decoded-size limit.
            asset_ref = "data:image/png;base64," + base64.b64encode(card).decode("ascii")
        except Exception:
            return scenes
        for scene in scenes:
            if scene.get("asset_type") == "brand_card" and not scene.get("asset_ref"):
                scene["asset_ref"] = asset_ref
        return scenes

    def worker_payload(self, brief: ShortBrief, studio_job_id: int | str | None = None) -> dict:
        preset = voice(brief.voice_preset)
        payload = {
            "video_subject": brief.title,
            "video_script": brief.voiceover,
            "video_aspect": "9:16",
            "video_source": "scene_assets",
            "video_count": 1,
            "brand_channel": brief.channel,
            "hook_text": brief.hook,
            "cta_text": brief.cta,
            "caption": brief.caption,
            "music_mood": brief.music_mood,
            "voice_preset": brief.voice_preset,
            "voice_provider": preset.provider,
            "voice_name": preset.voice,
            "voice_rate": preset.speed,
            "voice_asset_ref": brief.metadata.get("voice_asset_ref", ""),
            "subtitle_enabled": True,
            "subtitle_preset": brief.subtitle_preset,
            "scenes": self._scene_payloads(brief),
            "video_terms": [scene.visual for scene in brief.scenes if scene.visual][:7],
            "draft_id": brief.draft_id,
            "channel": brief.channel,
            "delivery_preset": brief.delivery_preset,
        }
        if studio_job_id is not None:
            payload["studio_job_id"] = str(studio_job_id)
        return payload

    def _required(self, job_id: int | str) -> ShortBrief:
        brief = self.sessions.load(job_id)
        if brief is None:
            raise KeyError(f"Shorts job {job_id} not found")
        return brief
