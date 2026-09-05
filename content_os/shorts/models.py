from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class ShortStage(StrEnum):
    """Stages are intentionally independent so a later edit can invalidate only what follows it."""

    SCRIPT = "script"
    VOICE = "voice"
    SCENES = "scenes"
    CAPTIONS = "captions"
    RENDER = "render"
    READY = "ready"


@dataclass(slots=True)
class ShortScene:
    seconds: float
    visual: str
    screen_text: str = ""
    asset_type: str = "stock_video"
    asset_ref: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ShortScene":
        return cls(
            seconds=float(value.get("seconds") or 0),
            visual=str(value.get("visual") or "").strip(),
            screen_text=str(value.get("screen_text") or "").strip(),
            asset_type=str(value.get("asset_type") or "stock_video").strip(),
            asset_ref=str(value.get("asset_ref") or "").strip(),
        )


@dataclass(slots=True)
class ShortBrief:
    title: str
    hook: str
    voiceover: str
    scenes: list[ShortScene]
    caption: str
    music_mood: str
    cta: str
    channel: str
    draft_id: int | str | None = None
    delivery_preset: str = "punchy"
    voice_preset: str = "auto_ru"
    subtitle_preset: str = "punch"
    stage: ShortStage = ShortStage.SCRIPT
    approved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_legacy(cls, data: dict[str, Any]) -> "ShortBrief":
        return cls(
            title=str(data.get("title") or "").strip(),
            hook=str(data.get("hook") or "").strip(),
            voiceover=str(data.get("voiceover") or "").strip(),
            scenes=[ShortScene.from_dict(x) for x in data.get("scenes") or []],
            caption=str(data.get("caption") or "").strip(),
            music_mood=str(data.get("music_mood") or "").strip(),
            cta=str(data.get("cta") or "").strip(),
            channel=str(data.get("channel") or "").strip(),
            draft_id=data.get("draft_id"),
        )

    @property
    def word_count(self) -> int:
        return len(self.voiceover.split())

    @property
    def duration(self) -> float:
        return round(sum(scene.seconds for scene in self.scenes), 2)

    def approve_script(self) -> None:
        self.approved = True
        self.stage = ShortStage.VOICE

    def invalidate_from(self, stage: ShortStage) -> None:
        """Mark the earliest stage that needs rebuilding after a targeted edit."""
        self.stage = stage
        if stage == ShortStage.SCRIPT:
            self.approved = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["stage"] = self.stage.value
        return value
