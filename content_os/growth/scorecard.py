from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ContentScore:
    content_id: str
    attention: float
    action: float
    revenue: float
    total: float
    sample_quality: str


def score_content(row: Mapping) -> ContentScore:
    views = max(0.0, float(row.get("views") or 0))
    reactions = max(0.0, float(row.get("reactions") or 0))
    shares = max(0.0, float(row.get("shares") or 0))
    clicks = max(0.0, float(row.get("clicks") or 0))
    leads = max(0.0, float(row.get("leads") or 0))
    orders = max(0.0, float(row.get("orders") or 0))
    sales = max(0.0, float(row.get("sales") or 0))
    revenue = max(0.0, float(row.get("revenue") or 0))
    attention = ((reactions + shares * 2) / views * 100) if views else 0.0
    action = ((clicks + leads * 2 + orders * 4 + sales * 8) / views * 100) if views else 0.0
    # Revenue is reported, not allowed to dominate an arbitrary synthetic score.
    total = attention * 0.35 + action * 0.65
    quality = "high" if views >= 1000 else "medium" if views >= 250 else "low"
    return ContentScore(str(row.get("content_id") or ""), attention, action, revenue, total, quality)


def rank_content(rows: list[Mapping], minimum_quality: str = "medium") -> list[ContentScore]:
    threshold = {"low": 0, "medium": 1, "high": 2}[minimum_quality]
    level = {"low": 0, "medium": 1, "high": 2}
    scores = [score_content(row) for row in rows]
    return sorted((s for s in scores if level[s.sample_quality] >= threshold), key=lambda s: s.total, reverse=True)
