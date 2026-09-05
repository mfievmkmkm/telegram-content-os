from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from .experiments import Experiment, validate_experiment


@dataclass(frozen=True)
class ExperimentDecision:
    status: str
    control_mean: float = 0.0
    challenger_mean: float = 0.0
    lift_percent: float = 0.0
    reason: str = ""


def decide_experiment(experiment: Experiment, control: Iterable[float], challenger: Iterable[float], minimum_lift_percent: float = 10.0) -> ExperimentDecision:
    """Make a conservative directional decision, not a fake statistical claim."""
    validate_experiment(experiment)
    a, b = list(control), list(challenger)
    if len(a) < experiment.minimum_samples or len(b) < experiment.minimum_samples:
        return ExperimentDecision("collecting", reason="not enough samples")
    a_mean, b_mean = mean(a), mean(b)
    lift = ((b_mean - a_mean) / a_mean * 100) if a_mean else (100.0 if b_mean > 0 else 0.0)
    if lift >= minimum_lift_percent:
        status = "challenger_leads"
    elif lift <= -minimum_lift_percent:
        status = "control_leads"
    else:
        status = "inconclusive"
    return ExperimentDecision(status, a_mean, b_mean, lift, "directional only; no significance claim")
