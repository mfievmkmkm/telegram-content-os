from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

EXPERIMENT_FIELDS = ("hook", "format", "topic", "angle", "length", "visual", "cta", "time", "offer")


@dataclass(frozen=True)
class ExperimentVariant:
    name: str
    values: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Experiment:
    hypothesis: str
    primary_variable: str
    control: ExperimentVariant
    challenger: ExperimentVariant
    success_metric: str
    minimum_samples: int = 2


def changed_variables(control: ExperimentVariant, challenger: ExperimentVariant) -> set[str]:
    keys = set(control.values) | set(challenger.values)
    return {key for key in keys if control.values.get(key) != challenger.values.get(key)}


def validate_experiment(experiment: Experiment) -> None:
    if experiment.primary_variable not in EXPERIMENT_FIELDS:
        raise ValueError(f"unsupported primary variable: {experiment.primary_variable}")
    if not experiment.hypothesis.strip():
        raise ValueError("experiment needs a hypothesis")
    if not experiment.success_metric.strip():
        raise ValueError("experiment needs a success metric")
    if experiment.minimum_samples < 2:
        raise ValueError("minimum_samples must be at least 2")
    changed = changed_variables(experiment.control, experiment.challenger)
    if changed != {experiment.primary_variable}:
        raise ValueError(
            "one experiment must change exactly one primary variable; "
            f"changed={sorted(changed)} expected={experiment.primary_variable}"
        )
