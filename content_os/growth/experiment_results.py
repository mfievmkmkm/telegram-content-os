from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from .experiments import Experiment, validate_experiment


@dataclass(frozen=True)
class ExperimentResult:
    status: str
    control_mean: float
    challenger_mean: float
    uplift_percent: float
    recommendation: str


def evaluate(experiment: Experiment, control_scores: Iterable[float], challenger_scores: Iterable[float], min_uplift_percent: float = 10.0) -> ExperimentResult:
    """Evaluate a controlled test without pretending statistical significance.

    The result can recommend another test or a provisional winner. It never mutates
    production settings and deliberately calls the winner provisional.
    """
    validate_experiment(experiment)
    control = [float(x) for x in control_scores]
    challenger = [float(x) for x in challenger_scores]
    if len(control) < experiment.minimum_samples or len(challenger) < experiment.minimum_samples:
        return ExperimentResult("collecting", mean(control) if control else 0.0, mean(challenger) if challenger else 0.0, 0.0, "Продолжить сбор данных")
    left, right = mean(control), mean(challenger)
    uplift = ((right - left) / abs(left) * 100.0) if left else (100.0 if right > 0 else 0.0)
    if uplift >= min_uplift_percent:
        return ExperimentResult("provisional_challenger", left, right, uplift, "Challenger выглядит сильнее; повторить тест перед закреплением")
    if uplift <= -min_uplift_percent:
        return ExperimentResult("provisional_control", left, right, uplift, "Control выглядит сильнее; повторить тест перед закреплением")
    return ExperimentResult("inconclusive", left, right, uplift, "Разница мала; не менять стратегию и проверить другую гипотезу")
