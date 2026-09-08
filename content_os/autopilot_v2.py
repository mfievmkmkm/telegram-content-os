from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from .football_challenges import Challenge, daily_challenge
from .meme_engine import MemeConcept, build_meme
from .planner_v2 import ContentCandidate, DailyPlan, PlannedItem, plan_day


@dataclass(frozen=True)
class AutopilotAction:
    project: str
    kind: str
    title: str
    payload: object
    requires_review: bool = True


@dataclass(frozen=True)
class AutopilotPlan:
    editorial: DailyPlan
    actions: tuple[AutopilotAction, ...] = field(default_factory=tuple)

    @property
    def publishable_without_review(self) -> bool:
        # Intentionally false until real production feedback proves the loop.
        return False


def _action_for(item: PlannedItem, recent_meme_fingerprints: Iterable[str], day: date) -> AutopilotAction:
    kind = item.kind.lower().strip()
    project = item.project.lower().strip()

    if kind == "meme":
        meme: MemeConcept = build_meme(project, item.topic, recent_meme_fingerprints)
        return AutopilotAction(project, "meme", item.topic, meme)

    if kind in {"challenge", "football_challenge"} and project in {"liga", "ligaprogress"}:
        challenge: Challenge = daily_challenge("community", "all", day)
        return AutopilotAction(project, "challenge", challenge.title, challenge)

    # Posts/shorts/remix are handed to the existing Content Factory. The payload is
    # intentionally factual/editorial metadata, not generated publish-ready prose.
    payload = {
        "topic": item.topic,
        "source": item.source,
        "reason": item.reason,
        "score": item.score,
        "next_stage": "content_factory",
    }
    return AutopilotAction(project, kind or "post", item.topic, payload)


def build_autopilot_plan(
    candidates: Iterable[ContentCandidate],
    recent_kinds: dict[str, list[str]] | None = None,
    recent_meme_fingerprints: Iterable[str] = (),
    day: date | None = None,
    per_project: int = 3,
) -> AutopilotPlan:
    """Plan the day and prepare reviewable actions; never auto-publish."""
    day = day or date.today()
    editorial = plan_day(candidates, recent_kinds=recent_kinds, per_project=per_project)
    actions = tuple(_action_for(item, recent_meme_fingerprints, day) for item in editorial.items)
    return AutopilotPlan(editorial, actions)
