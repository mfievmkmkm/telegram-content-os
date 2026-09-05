from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

from .taxonomy import KNOWLEDGE_AREAS, classify_text


@dataclass(frozen=True)
class KnowledgeQuery:
    task: str
    project: str = ""
    areas: tuple[str, ...] = ()
    limit: int = 8


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zа-яё0-9]{4,}", (text or "").lower())}


def retrieve(rows: Iterable[Mapping], query: KnowledgeQuery) -> list[Mapping]:
    """Retrieve practical, source-diverse notes for a concrete task.

    No course text is published from here. The result is evidence for a later
    synthesis step, keeping retrieval separate from generation.
    """
    rows = list(rows)
    query_tokens = _tokens(query.task + " " + query.project)
    wanted = set(query.areas)
    if not wanted:
        wanted = {area.key for area in classify_text(query.task + " " + query.project, limit=4)}
    area_terms = {
        term
        for area in KNOWLEDGE_AREAS
        if area.key in wanted
        for term in area.terms
    }

    ranked = []
    for index, row in enumerate(rows):
        text = str(row.get("text", "") if isinstance(row, dict) else row["text"])
        lowered = text.lower()
        overlap = len(query_tokens & _tokens(text))
        area_hits = sum(lowered.count(term) for term in area_terms)
        practical = sum(lowered.count(term) for term in ("шаг", "чеклист", "пример", "сделай", "нужно", "формула", "правило", "ошиб"))
        score = overlap * 5 + area_hits * 2 + min(practical, 5)
        if score:
            ranked.append((score, -index, row))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = []
    per_source: dict[str, int] = {}
    for _, _, row in ranked:
        source = str(row.get("source_channel", "") if isinstance(row, dict) else row["source_channel"])
        if per_source.get(source, 0) >= 2:
            continue
        selected.append(row)
        per_source[source] = per_source.get(source, 0) + 1
        if len(selected) >= max(1, min(query.limit, 12)):
            break
    return selected
