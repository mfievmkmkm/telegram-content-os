from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping
from urllib.parse import parse_qsl, urlencode

_ALLOWED = {"project", "content", "format", "offer", "campaign"}


@dataclass(frozen=True)
class CampaignRef:
    project: str
    content: str
    format: str = ""
    offer: str = ""
    campaign: str = ""

    def token(self) -> str:
        values = {
            "project": self.project,
            "content": self.content,
            "format": self.format,
            "offer": self.offer,
            "campaign": self.campaign,
        }
        return urlencode([(key, value) for key, value in values.items() if value])

    @classmethod
    def parse(cls, token: str) -> "CampaignRef":
        values = {key: value for key, value in parse_qsl(token) if key in _ALLOWED}
        if not values.get("project") or not values.get("content"):
            raise ValueError("campaign token must contain project and content")
        return cls(**values)


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
    def lead_to_sale(self) -> float:
        return self.sales / self.leads * 100 if self.leads else 0.0


def build_funnel_summary(events: Iterable[Mapping], source_token: str) -> FunnelSummary:
    counts = {"visit": 0, "bot_start": 0, "lead": 0, "order": 0, "sale": 0}
    revenue = 0.0
    for event in events:
        if str(event.get("source") or "") != source_token:
            continue
        event_type = str(event.get("event_type") or "")
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
