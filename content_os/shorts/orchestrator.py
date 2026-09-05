from __future__ import annotations

from dataclasses import asdict

from .models import ShortBrief, ShortStage
from .presets import voice
from .script import ShortScriptService
from .session import ShortSessionStore


class ShortsStudio:
    """Coordinates review-first Shorts production without coupling Telegram UI to rendering details."""

    def __init__(self, editor, database, legacy_video_factory):
        self.scripts = ShortScriptService(editor)
        self.sessions = ShortSessionStore(database)
        self.renderer = legacy_video_factory

    async def start(self, draft, delivery_key: str = "punchy") -> tuple[int | str, ShortBrief]:
        brief = await self.scripts.prepare(draft, delivery_key)
        # Reuse the existing video-job table to keep IDs stable across old/new UI.
        payload = self.worker_payload(brief)
        job_id = self.renderer.db.save_video_job(draft["id"], __import__("json").dumps(payload, ensure_ascii=False, indent=2))
        self.sessions.save(job_id, brief)
        return job_id, brief

    async def rewrite(self, job_id: int | str, mode: str) -> ShortBrief:
        current = self._required(job_id)
        updated = await self.scripts.rewrite(current, mode)
        return self.sessions.replace_script(job_id, updated)

    def choose_voice(self, job_id: int | str, preset_key: str) -> ShortBrief:
        voice(preset_key)  # normalize unknown keys to a safe preset through the domain registry
        return self.sessions.choose_voice(job_id, preset_key if preset_key in __import__("content_os.shorts.presets", fromlist=["VOICE_PRESETS"]).VOICE_PRESETS else "auto_ru")

    def choose_style(self, job_id: int | str, preset_key: str) -> ShortBrief:
        from .presets import DELIVERY_PRESETS
        normalized = preset_key if preset_key in DELIVERY_PRESETS else "punchy"
        return self.sessions.choose_style(job_id, normalized)

    def approve(self, job_id: int | str) -> ShortBrief:
        return self.sessions.approve(job_id)

    async def render(self, job_id: int | str, progress=None):
        brief = self._required(job_id)
        if not brief.approved:
            raise RuntimeError("Сначала подтверди сценарий")
        payload = self.worker_payload(brief)
        return await self.renderer.render(payload, progress)

    def worker_payload(self, brief: ShortBrief) -> dict:
        preset = voice(brief.voice_preset)
        scenes = [asdict(scene) for scene in brief.scenes]
        return {
            "title": brief.title,
            "hook": brief.hook,
            "voiceover": brief.voiceover,
            "caption": brief.caption,
            "music_mood": brief.music_mood,
            "cta": brief.cta,
            "draft_id": brief.draft_id,
            "channel": brief.channel,
            "aspect_ratio": "9:16",
            "language": "ru",
            "delivery_preset": brief.delivery_preset,
            "voice_preset": brief.voice_preset,
            "voice_provider": preset.provider,
            "voice_name": preset.voice,
            "voice_rate": preset.speed,
            "subtitle_preset": brief.subtitle_preset,
            "scenes": scenes,
        }

    def _required(self, job_id: int | str) -> ShortBrief:
        brief = self.sessions.load(job_id)
        if brief is None:
            raise KeyError(f"Shorts job {job_id} not found")
        return brief
