from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from ..campaigns import CampaignRef, campaign_source, parse_campaign


_EVENT_ALIASES = {
    "landing": "visit",
    "visit": "visit",
    "bot_start": "bot_start",
    "recommendation": "lead",
    "lead": "lead",
    "offer_view": "lead",
    "order_created": "order",
    "order": "order",
    "paid": "sale",
    "payment": "sale",
    "sale": "sale",
}


@dataclass(frozen=True)
class FunnelSummary:
    visits: int = 0
    bot_starts: int = 0
    leads: int = 0
    orders: int = 0
    sales: int = 0
    revenue: float = 0.0

    @property
    def visit_to_start(self) -> float:
        return self.bot_starts / self.visits * 100 if self.visits else 0.0

    @property
    def lead_to_order(self) -> float:
        return self.orders / self.leads * 100 if self.leads else 0.0

    @property
    def lead_to_sale(self) -> float:
        return self.sales / self.leads * 100 if self.leads else 0.0

    @property
    def order_to_sale(self) -> float:
        return self.sales / self.orders * 100 if self.orders else 0.0


def normalize_event_type(event_type: str) -> str:
    return _EVENT_ALIASES.get((event_type or "").strip().lower(), "")


def source_matches(event_source: str, source_token: str) -> bool:
    """Match both compact Telegram payload tokens and canonical source strings."""
    event_source = str(event_source or "").strip()
    source_token = str(source_token or "").strip()
    if event_source == source_token:
        return True

    left = parse_campaign(event_source)
    right = parse_campaign(source_token)
    if left and right:
        return left == right
    if left:
        return campaign_source(left) == source_token
    if right:
        return campaign_source(right) == event_source
    return False


def build_funnel_summary(events: Iterable[Mapping], source_token: str) -> FunnelSummary:
    counts = {"visit": 0, "bot_start": 0, "lead": 0, "order": 0, "sale": 0}
    revenue = 0.0
    for event in events:
        if not source_matches(str(event.get("source") or ""), source_token):
            continue
        event_type = normalize_event_type(str(event.get("event_type") or ""))
        if event_type in counts:
            counts[event_type] += 1
        if event_type == "sale":
            revenue += float(event.get("revenue") or 0)
    return FunnelSummary(
        visits=counts["visit"],
        bot_starts=counts["bot_start"],
        leads=counts["lead"],
        orders=counts["order"],
        sales=counts["sale"],
        revenue=revenue,
    )


__all__ = [
    "CampaignRef",
    "FunnelSummary",
    "build_funnel_summary",
    "campaign_source",
    "normalize_event_type",
    "parse_campaign",
    "source_matches",
]
