from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class GrowthInsight:
    dimension: str
    value: str
    metric: str
    score: float
    samples: int
    confidence: str


def _confidence(samples: int) -> str:
    if samples >= 12:
        return "high"
    if samples >= 5:
        return "medium"
    return "low"


def rank_dimension(
    rows: Iterable[Mapping],
    dimension: str,
    metric: str,
    minimum_samples: int = 2,
) -> tuple[GrowthInsight, ...]:
    """Aggregate observed performance without pretending causality.

    Rows are expected to contain a dimension value and a numeric metric. Results are
    descriptive only; low-sample winners are explicitly labelled low confidence.
    """
    buckets: dict[str, list[float]] = {}
    for row in rows:
        value = str(row.get(dimension) or "").strip()
        if not value:
            continue
        try:
            number = float(row.get(metric) or 0)
        except (TypeError, ValueError):
            continue
        buckets.setdefault(value, []).append(number)

    insights: list[GrowthInsight] = []
    for value, numbers in buckets.items():
        if len(numbers) < max(1, minimum_samples):
            continue
        score = sum(numbers) / len(numbers)
        insights.append(GrowthInsight(dimension, value, metric, score, len(numbers), _confidence(len(numbers))))
    insights.sort(key=lambda item: (item.score, item.samples), reverse=True)
    return tuple(insights)


def best_observed(
    rows: Iterable[Mapping],
    dimension: str,
    metric: str,
    minimum_samples: int = 2,
) -> GrowthInsight | None:
    ranked = rank_dimension(rows, dimension, metric, minimum_samples)
    return ranked[0] if ranked else None
