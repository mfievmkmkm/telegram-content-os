from __future__ import annotations

import re
from dataclasses import dataclass

from .channels import CHANNELS, CONTENT_LANES
from .formatting import plain_text


_STOP = {
    "как", "что", "это", "для", "или", "без", "почему", "после", "перед", "когда",
    "только", "может", "один", "одна", "всегда", "ещё", "уже", "свой", "свои", "если",
}


def _tokens(value: str) -> set[str]:
    return {
        word if len(word) <= 6 else word[:6]
        for word in re.findall(r"[a-zа-яё0-9]{4,}", plain_text(value).lower())
        if word not in _STOP
    }


def topical_similarity(left: str, right: str) -> float:
    """Small, deterministic novelty check that works without embeddings."""
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


@dataclass(frozen=True, slots=True)
class TopicChoice:
    lane: str
    seed: str


class TopicRotation:
    """Persistent editorial rotation with a recent-topic exclusion window."""

    def __init__(self, db):
        self.db = db

    def recent(self, project: str, limit: int = 18) -> list[str]:
        try:
            rows = list(self.db.recent_drafts(project, limit))
        except Exception:
            return []
        result = []
        for row in rows:
            try:
                value = row.get("source_title") or row.get("text") if hasattr(row, "get") else row["text"]
            except Exception:
                value = ""
            if value:
                result.append(str(value))
        return result

    def choices(self, project: str, count: int = 8, advance: bool = False) -> list[TopicChoice]:
        lanes = tuple(CONTENT_LANES[project])
        seeds = tuple(CHANNELS[project].get("topics") or ())
        counter = int(self.db.get(f"topic_rotation:{project}") or 0)
        recent = self.recent(project)
        ranked: list[tuple[float, int, TopicChoice]] = []
        pool_size = max(len(lanes), len(seeds))
        for offset in range(pool_size):
            lane = lanes[(counter + offset) % len(lanes)]
            seed = seeds[(counter + offset) % len(seeds)]
            candidate = f"{lane}. {seed}"
            similarity = max((topical_similarity(candidate, item) for item in recent), default=0.0)
            ranked.append((similarity, offset, TopicChoice(lane, seed)))
        ranked.sort(key=lambda item: (item[0] >= .48, item[0], item[1]))
        selected = [item[2] for item in ranked[:count]]
        if advance and selected:
            self.db.set(f"topic_rotation:{project}", str(counter + 1))
        return selected

    def next(self, project: str) -> TopicChoice:
        return self.choices(project, 1, advance=True)[0]
