from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .experiments import Experiment, ExperimentVariant, validate_experiment
from .recommendations import GrowthRecommendation, recommendation_pack


@dataclass(frozen=True)
class FeedbackExperiment:
    recommendation: GrowthRecommendation
    experiment: Experiment


_DIMENSION_MAP = {
    "hook_type": "hook",
    "format": "format",
    "visual_type": "visual",
    "publish_hour": "time",
    "offer": "offer",
}


def build_feedback_experiments(
    rows: Iterable[Mapping],
    project: str,
    baseline: Mapping[str, str] | None = None,
    minimum_samples: int = 5,
) -> tuple[FeedbackExperiment, ...]:
    """Convert observed winners into one-variable experiments for human review.

    Nothing here edits the calendar or publishes content. Each proposal changes exactly
    one primary variable so the downstream comparison remains interpretable.
    """
    data = list(rows)
    baseline = dict(baseline or {})
    recommendations = []
    # recommendation_pack currently uses its own conservative sample floor. Filter the
    # rows here when callers ask for a stricter minimum without weakening defaults.
    for item in recommendation_pack(data, project):
        scoped_count = sum(
            1
            for row in data
            if str(row.get("project") or "").strip().lower() == project.lower()
            and str(row.get(item.dimension) or "").strip() == item.value
        )
        if scoped_count >= max(5, minimum_samples):
            recommendations.append(item)

    result = []
    for item in recommendations:
        primary = _DIMENSION_MAP.get(item.dimension)
        if not primary:
            continue
        current = str(baseline.get(primary) or "control")
        control_values = dict(baseline)
        challenger_values = dict(baseline)
        control_values[primary] = current
        challenger_values[primary] = item.value
        if challenger_values[primary] == control_values[primary]:
            continue
        experiment = Experiment(
            hypothesis=f"Observed {item.dimension}={item.value} may improve {item.metric} for {project}",
            primary_variable=primary,
            control=ExperimentVariant("control", control_values),
            challenger=ExperimentVariant("challenger", challenger_values),
            success_metric=item.metric,
            minimum_samples=max(2, minimum_samples),
        )
        validate_experiment(experiment)
        result.append(FeedbackExperiment(item, experiment))
    return tuple(result)
