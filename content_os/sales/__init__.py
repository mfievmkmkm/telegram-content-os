"""Sales Engine: outcome-first catalog, diagnosis and order lifecycle."""

from .catalog import PACKAGES, SalesPackage, package
from .diagnostic import DiagnosticInput, Recommendation, recommend
from .lifecycle import ORDER_STATES, OrderTransition, can_transition, next_actions

__all__ = [
    "PACKAGES",
    "SalesPackage",
    "package",
    "DiagnosticInput",
    "Recommendation",
    "recommend",
    "ORDER_STATES",
    "OrderTransition",
    "can_transition",
    "next_actions",
]
