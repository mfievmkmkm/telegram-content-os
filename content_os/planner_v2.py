from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class ContentCandidate:
    project: str
    kind: str
    topic: str
    source: str = ""
    freshness: float = 0.5
    relevance: float = 0.5
    novelty: float = 0.5
    evidence: float = 0.5
    sales_value: float = 0.0
    urgency: float = 0.0
    fact_sensitive: bool = False

    @property
    def score(self) -> float:
        # Editorial usefulness dominates raw sales value. Urgency matters, but cannot
        # rescue a weak/unverified idea on its own.
        value = (
            self.freshness * 0.20
            + self.relevance * 0.25
            + self.novelty * 0.20
            + self.evidence * 0.20
            + self.sales_value * 0.08
            + self.urgency * 0.07
        )
        if self.fact_sensitive and self.evidence < 0.65:
            value -= 0.35
        return max(0.0, min(value, 1.0))


@dataclass(frozen=True)
class PlannedItem:
    project: str
    kind: str
    topic: str
    reason: str
    score: int
    source: str = ""


@dataclass(frozen=True)
class DailyPlan:
    items: tuple[PlannedItem, ...] = field(default_factory=tuple)
    rejected: tuple[str, ...] = field(default_factory=tuple)


def plan_day(
    candidates: Iterable[ContentCandidate],
    recent_kinds: dict[str, list[str]] | None = None,
    per_project: int = 3,
    minimum_score: float = 0.52,
) -> DailyPlan:
    """Build a reviewable day plan. Never publishes automatically."""
    recent_kinds = recent_kinds or {}
    grouped: dict[str, list[ContentCandidate]] = {}
    rejected: list[str] = []
    for candidate in candidates:
        if not candidate.topic.strip():
            continue
        if candidate.score < minimum_score:
            rejected.append(candidate.topic)
            continue
        grouped.setdefault(candidate.project, []).append(candidate)

    selected: list[PlannedItem] = []
    for project, rows in grouped.items():
        rows.sort(key=lambda item: (item.score, item.novelty, item.freshness), reverse=True)
        last_kind = (recent_kinds.get(project) or [""])[-1]
        used_topics: set[str] = set()
        count = 0
        for candidate in rows:
            normalized = candidate.topic.lower().strip()
            if normalized in used_topics:
                continue
            # Do not repeat the same format immediately if an almost-as-good
            # alternative exists. This prevents mechanical content calendars.
            if candidate.kind == last_kind:
                alternative = next((x for x in rows if x.kind != last_kind and x.topic.lower().strip() not in used_topics and x.score >= candidate.score - 0.10), None)
                if alternative is not None:
                    candidate = alternative
                    normalized = candidate.topic.lower().strip()
            used_topics.add(normalized)
            reason_bits = []
            if candidate.freshness >= .8: reason_bits.append("свежий инфоповод")
            if candidate.novelty >= .8: reason_bits.append("необычный угол")
            if candidate.evidence >= .8: reason_bits.append("сильная фактическая база")
            if candidate.sales_value >= .7: reason_bits.append("есть нативный переход в продукт")
            if not reason_bits: reason_bits.append("лучший редакторский баланс на сегодня")
            selected.append(PlannedItem(project, candidate.kind, candidate.topic, ", ".join(reason_bits), round(candidate.score * 100), candidate.source))
            last_kind = candidate.kind
            count += 1
            if count >= max(1, per_project):
                break

    selected.sort(key=lambda item: (-item.score, item.project))
    return DailyPlan(tuple(selected), tuple(rejected))
