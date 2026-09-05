from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .playbooks import Playbook, build_playbook
from .retrieval import KnowledgeQuery, retrieve


@dataclass(frozen=True)
class GenerationGuidance:
    project: str
    task: str
    playbook: Playbook
    system_rules: tuple[str, ...]

    @property
    def prompt_context(self) -> str:
        rules = "\n".join(f"- {rule}" for rule in self.system_rules)
        return f"ПРАВИЛА ПРИМЕНЕНИЯ ЗНАНИЙ:\n{rules}\n\n{self.playbook.prompt_context}"


def guidance_for_task(rows: Iterable[Mapping], task: str, project: str, limit: int = 7) -> GenerationGuidance:
    """Retrieve course knowledge as editorial guidance, never as factual evidence.

    Course material can shape hooks, structure, offers and checks. It cannot prove a
    current market fact, price, football event, statistic or guaranteed result.
    """
    query = KnowledgeQuery(task=task, project=project, limit=limit)
    selected = retrieve(rows, query)
    playbook = build_playbook(f"{project}: {task}", selected)
    rules = (
        "Используй знания как принципы и чеклист, а не как источник текущих фактов.",
        "Не копируй авторские формулировки и не упоминай курс без отдельной задачи.",
        "Любые цены, проценты, даты, статистику и рыночные утверждения бери только из fact pack текущего материала.",
        "Не обещай результат и не превращай корреляцию или кейс из курса в универсальное правило.",
        "Сохраняй голос конкретного проекта; знания должны усиливать материал, а не делать его лекцией.",
    )
    return GenerationGuidance(project=project, task=task, playbook=playbook, system_rules=rules)
