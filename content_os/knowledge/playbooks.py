from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .taxonomy import classify_text


@dataclass(frozen=True)
class Playbook:
    task: str
    areas: tuple[str, ...]
    evidence: tuple[str, ...]
    prompt_context: str


def build_playbook(task: str, rows: Iterable[Mapping], max_chars: int = 6000) -> Playbook:
    """Package retrieved notes for synthesis without presenting them as authored copy."""
    areas = tuple(area.key for area in classify_text(task, limit=4))
    evidence = []
    used = 0
    for row in rows:
        text = str(row.get("text", "") if isinstance(row, dict) else row["text"]).strip()
        if not text:
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        excerpt = text[:remaining]
        evidence.append(excerpt)
        used += len(excerpt)
    context = (
        "Используй материалы ниже только как базу принципов и проверок. "
        "Не копируй формулировки, названия курса или автора в итоговый материал. "
        "Не добавляй цифры и обещания, если они не подтверждены данными текущей задачи.\n\n"
        + "\n\n---\n\n".join(evidence)
    )
    return Playbook(task=task, areas=areas, evidence=tuple(evidence), prompt_context=context)
