from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class VisualConcept:
    key: str
    label: str
    asset_type: str
    density: str
    mood: str


LIBRARY = {
    "gifts": (
        VisualConcept("terminal", "Market Terminal", "market_chart", "medium", "analytical"),
        VisualConcept("collectible", "Collectible Focus", "screenshot", "low", "premium"),
        VisualConcept("warning", "Risk Signal", "brand_card", "low", "urgent"),
        VisualConcept("meme", "Market Meme", "meme", "low", "playful"),
        VisualConcept("number", "One Number", "brand_card", "minimal", "editorial"),
        VisualConcept("compare", "A / B", "brand_card", "medium", "analytical"),
    ),
    "liga": (
        VisualConcept("tactics", "Tactics Board", "brand_card", "medium", "analytical"),
        VisualConcept("tunnel", "Stadium Tunnel", "stock_video", "low", "cinematic"),
        VisualConcept("training", "Training Detail", "stock_video", "low", "sport"),
        VisualConcept("mistake", "Decision Freeze", "brand_card", "medium", "urgent"),
        VisualConcept("challenge", "Challenge Card", "brand_card", "medium", "energetic"),
        VisualConcept("meme", "Locker Room Meme", "meme", "low", "playful"),
    ),
}


def choose_concepts(channel: str, recent_keys: Iterable[str] = (), count: int = 3) -> list[VisualConcept]:
    pool = list(LIBRARY.get(channel, LIBRARY["liga"]))
    recent = list(recent_keys)
    # Aesthetic rule: first prefer compositions not used recently; never randomize the brand language.
    fresh = [item for item in pool if item.key not in recent[-5:]]
    repeated = [item for item in pool if item.key in recent[-5:]]
    return (fresh + repeated)[:max(1, min(count, len(pool)))]


def concept_rows(channel: str, recent_keys: Iterable[str] = ()) -> list[dict]:
    return [
        {"key": item.key, "label": item.label, "asset_type": item.asset_type, "density": item.density, "mood": item.mood}
        for item in choose_concepts(channel, recent_keys)
    ]
