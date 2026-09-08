from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .insights import best_observed


@dataclass(frozen=True)
class GrowthRecommendation:
    project: str
    dimension: str
    value: str
    metric: str
    confidence: str
    action: str
    reason: str


def recommend(
    rows: Iterable[Mapping],
    project: str,
    dimension: str,
    metric: str,
    minimum_samples: int = 5,
) -> GrowthRecommendation | None:
    """Turn descriptive observations into a review-only recommendation.

    This never changes scheduling/content automatically. Low-sample observations are
    intentionally suppressed so the system cannot overfit a couple of lucky posts.
    """
    scoped = [row for row in rows if str(row.get("project") or "").strip().lower() == project.lower()]
    insight = best_observed(scoped, dimension, metric, minimum_samples=minimum_samples)
    if insight is None or insight.confidence == "low":
        return None
    return GrowthRecommendation(
        project=project,
        dimension=dimension,
        value=insight.value,
        metric=metric,
        confidence=insight.confidence,
        action=f"Протестировать ещё один материал с {dimension}={insight.value}",
        reason=f"Лучшее наблюдаемое среднее {metric}: {insight.score:.3f} на {insight.samples} материалах. Это корреляция, не доказанная причина.",
    )


def recommendation_pack(rows: Iterable[Mapping], project: str) -> tuple[GrowthRecommendation, ...]:
    data = list(rows)
    checks = (
        ("hook_type", "engagement_rate"),
        ("format", "engagement_rate"),
        ("visual_type", "engagement_rate"),
        ("publish_hour", "engagement_rate"),
        ("offer", "conversion_rate"),
    )
    result = []
    for dimension, metric in checks:
        item = recommend(data, project, dimension, metric)
        if item:
            result.append(item)
    return tuple(result)
