from __future__ import annotations

import json

from .models import ShortBrief, ShortScene, ShortStage


class ShortSessionStore:
    """Small persistence adapter over the existing settings KV store.

    It keeps review state outside Telegram messages and survives Railway restarts.
    The backing database only needs get(key) and set(key, value), which both current
    SQLite and Supabase implementations already expose.
    """

    PREFIX = "shortsv2:job:"

    def __init__(self, database):
        self.db = database

    def save(self, job_id: int | str, brief: ShortBrief) -> None:
        self.db.set(self.PREFIX + str(job_id), json.dumps(brief.to_dict(), ensure_ascii=False))

    def load(self, job_id: int | str) -> ShortBrief | None:
        raw = self.db.get(self.PREFIX + str(job_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return ShortBrief(
            title=str(data.get("title") or ""),
            hook=str(data.get("hook") or ""),
            voiceover=str(data.get("voiceover") or ""),
            scenes=[ShortScene.from_dict(x) for x in data.get("scenes") or []],
            caption=str(data.get("caption") or ""),
            music_mood=str(data.get("music_mood") or ""),
            cta=str(data.get("cta") or ""),
            channel=str(data.get("channel") or ""),
            draft_id=data.get("draft_id"),
            delivery_preset=str(data.get("delivery_preset") or "punchy"),
            voice_preset=str(data.get("voice_preset") or "auto_ru"),
            subtitle_preset=str(data.get("subtitle_preset") or "punch"),
            stage=ShortStage(str(data.get("stage") or ShortStage.SCRIPT.value)),
            approved=bool(data.get("approved")),
            metadata=dict(data.get("metadata") or {}),
        )

    def choose_voice(self, job_id: int | str, voice_preset: str) -> ShortBrief:
        brief = self._required(job_id)
        brief.voice_preset = voice_preset
        brief.invalidate_from(ShortStage.VOICE)
        self.save(job_id, brief)
        return brief

    def choose_style(self, job_id: int | str, delivery_preset: str) -> ShortBrief:
        brief = self._required(job_id)
        brief.delivery_preset = delivery_preset
        brief.invalidate_from(ShortStage.SCRIPT)
        self.save(job_id, brief)
        return brief

    def choose_subtitle(self, job_id: int | str, subtitle_preset: str) -> ShortBrief:
        brief = self._required(job_id)
        brief.subtitle_preset = subtitle_preset
        brief.invalidate_from(ShortStage.CAPTIONS)
        self.save(job_id, brief)
        return brief

    def replace_scenes(self, job_id: int | str, scenes: list[ShortScene]) -> ShortBrief:
        brief = self._required(job_id)
        brief.scenes = scenes
        brief.invalidate_from(ShortStage.SCENES)
        self.save(job_id, brief)
        return brief

    def approve(self, job_id: int | str) -> ShortBrief:
        brief = self._required(job_id)
        brief.approve_script()
        self.save(job_id, brief)
        return brief

    def replace_script(self, job_id: int | str, updated: ShortBrief) -> ShortBrief:
        existing = self._required(job_id)
        updated.voice_preset = existing.voice_preset
        updated.subtitle_preset = existing.subtitle_preset
        updated.delivery_preset = existing.delivery_preset
        updated.stage = ShortStage.SCRIPT
        updated.approved = False
        self.save(job_id, updated)
        return updated

    def _required(self, job_id: int | str) -> ShortBrief:
        brief = self.load(job_id)
        if brief is None:
            raise KeyError(f"Shorts job {job_id} not found")
        return brief
