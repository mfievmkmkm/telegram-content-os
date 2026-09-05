from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Mapping

WINDOWS_HOURS = (1, 6, 24, 48)


def _dt(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result


@dataclass(frozen=True)
class GrowthSnapshot:
    age_hours: float
    views: int = 0
    reactions: int = 0
    forwards: int = 0
    comments: int = 0
    subscriber_delta: int | None = None
    clicks: int = 0
    leads: int = 0
    orders: int = 0
    sales: int = 0
    revenue: float = 0.0

    @property
    def engagement_rate(self) -> float:
        if not self.views:
            return 0.0
        return (self.reactions + self.forwards * 2 + self.comments * 2) / self.views * 100

    @property
    def click_rate(self) -> float:
        return self.clicks / self.views * 100 if self.views else 0.0

    @property
    def lead_rate(self) -> float:
        return self.leads / self.clicks * 100 if self.clicks else 0.0

    @property
    def sales_rate(self) -> float:
        return self.sales / self.leads * 100 if self.leads else 0.0


@dataclass(frozen=True)
class GrowthSummary:
    content_id: int | str
    windows: Mapping[int, GrowthSnapshot] = field(default_factory=dict)

    @property
    def latest(self) -> GrowthSnapshot | None:
        return max(self.windows.values(), key=lambda item: item.age_hours, default=None)


def _snapshot(row: Mapping, published_at: datetime) -> GrowthSnapshot:
    captured = _dt(row["captured_at"])
    age = max(0.0, (captured - published_at).total_seconds() / 3600)
    return GrowthSnapshot(
        age_hours=age,
        views=int(row.get("views") or 0),
        reactions=int(row.get("reactions") or 0),
        forwards=int(row.get("forwards") or 0),
        comments=int(row.get("comments") or 0),
        subscriber_delta=row.get("subscriber_delta"),
        clicks=int(row.get("clicks") or 0),
        leads=int(row.get("leads") or 0),
        orders=int(row.get("orders") or 0),
        sales=int(row.get("sales") or 0),
        revenue=float(row.get("revenue") or 0),
    )


def build_growth_summary(
    content_id: int | str,
    published_at: datetime | str,
    metric_rows: Iterable[Mapping],
    tolerance_ratio: float = 0.35,
) -> GrowthSummary:
    """Pick the first trustworthy measurement after each 1h/6h/24h/48h mark.

    A window never borrows an earlier measurement. That keeps a 19-hour snapshot
    from being labelled as a 24-hour result while still allowing a modestly late
    collector run (for example 24h20m) to fill the 24-hour window.
    """
    published = _dt(published_at)
    snapshots = sorted((_snapshot(row, published) for row in metric_rows), key=lambda item: item.age_hours)
    selected: dict[int, GrowthSnapshot] = {}
    for target in WINDOWS_HOURS:
        eligible = [item for item in snapshots if item.age_hours >= target]
        if not eligible:
            continue
        closest = eligible[0]
        tolerance = max(0.5, target * tolerance_ratio)
        if closest.age_hours - target <= tolerance:
            selected[target] = closest
    return GrowthSummary(content_id=content_id, windows=selected)
