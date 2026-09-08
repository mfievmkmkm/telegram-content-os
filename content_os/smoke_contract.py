from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SmokeStep:
    key: str
    title: str
    destructive: bool = False


SMOKE_STEPS: tuple[SmokeStep, ...] = (
    SmokeStep("boot", "V2 boots without polling/import errors"),
    SmokeStep("home", "Admin Home and TODAY open"),
    SmokeStep("draft", "Create one Liga and one Gifts draft"),
    SmokeStep("director", "Creative Director reviews and can block/rewrite"),
    SmokeStep("visuals", "A/B/C visual variants render and selection persists"),
    SmokeStep("shorts_script", "Shorts Studio reaches approved script"),
    SmokeStep("shorts_render", "SpeechKit + mixed-media worker renders preview"),
    SmokeStep("schedule", "Draft can be scheduled and cancelled"),
    SmokeStep("publish_private", "Publish test material to a private test destination", destructive=True),
    SmokeStep("growth", "Attribution event appears in Growth"),
    SmokeStep("sales", "Diagnostic creates a tracked test order", destructive=True),
    SmokeStep("restart", "State survives service restart"),
)


def remaining(completed: Iterable[str]) -> tuple[SmokeStep, ...]:
    done = {str(key).strip() for key in completed}
    return tuple(step for step in SMOKE_STEPS if step.key not in done)


def safe_phase() -> tuple[SmokeStep, ...]:
    return tuple(step for step in SMOKE_STEPS if not step.destructive)
