"""Growth layer: analytics windows, attribution and controlled experiments."""

from .analytics_v2 import GrowthSnapshot, GrowthSummary, build_growth_summary
from .attribution import CampaignRef, FunnelSummary, build_funnel_summary
from .experiments import Experiment, ExperimentVariant, validate_experiment

__all__ = [
    "GrowthSnapshot",
    "GrowthSummary",
    "build_growth_summary",
    "CampaignRef",
    "FunnelSummary",
    "build_funnel_summary",
    "Experiment",
    "ExperimentVariant",
    "validate_experiment",
]
