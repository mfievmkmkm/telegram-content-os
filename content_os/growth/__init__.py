"""Growth layer: analytics windows, attribution and controlled experiments."""

from .analytics_v2 import GrowthSnapshot, GrowthSummary, build_growth_summary
from .attribution import CampaignRef, FunnelSummary, build_funnel_summary
from .cta import TrackedCTA, telegram_deep_link
from .decision import ExperimentDecision, decide_experiment
from .experiments import Experiment, ExperimentVariant, validate_experiment
from .insights import GrowthInsight, best_observed, rank_dimension

__all__ = [
    "GrowthSnapshot",
    "GrowthSummary",
    "build_growth_summary",
    "CampaignRef",
    "FunnelSummary",
    "build_funnel_summary",
    "TrackedCTA",
    "telegram_deep_link",
    "ExperimentDecision",
    "decide_experiment",
    "Experiment",
    "ExperimentVariant",
    "validate_experiment",
    "GrowthInsight",
    "best_observed",
    "rank_dimension",
]
