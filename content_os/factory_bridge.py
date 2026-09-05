from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .autopilot_v2 import AutopilotAction
from .content_factory import FactoryPlan, FactoryRequest, build_factory_plan
from .knowledge.playbooks import build_playbook
from .knowledge.retrieval import KnowledgeQuery, retrieve


@dataclass(frozen=True)
class FactoryBridgeResult:
    action: AutopilotAction
    request: FactoryRequest
    plan: FactoryPlan
    knowledge_items: int


def _format_for(kind: str) -> str:
    key = (kind or "post").strip().lower()
    if key in {"short", "shorts", "reel"}:
        return "shorts"
    if key in {"meme", "challenge", "football_challenge", "poll"}:
        return key
    return "post"


def action_to_factory(
    action: AutopilotAction,
    knowledge_rows: Iterable[Mapping] = (),
    facts: Iterable[str] = (),
    source_refs: Iterable[str] = (),
    campaign_token: str = "",
) -> FactoryBridgeResult:
    """Convert one review-only Autopilot action into a Content Factory contract.

    Course/knowledge rows can shape the playbook, but facts and source_refs are kept
    separate so retrieved course notes can never silently become market evidence.
    """
    project = action.project.strip().lower()
    if project == "ligaprogress":
        project = "liga"
    topic = action.title.strip()
    query = KnowledgeQuery(task=f"{project} {_format_for(action.kind)} {topic}", project=project, limit=6)
    selected = retrieve(list(knowledge_rows), query) if knowledge_rows else []
    playbook = build_playbook(query.task, selected) if selected else None
    request = FactoryRequest(
        project=project,
        topic=topic,
        format=_format_for(action.kind),
        objective="engagement",
        facts=tuple(str(x).strip() for x in facts if str(x).strip()),
        source_refs=tuple(str(x).strip() for x in source_refs if str(x).strip()),
        knowledge_context=playbook.prompt_context if playbook else "",
        campaign_token=campaign_token,
    )
    plan = build_factory_plan(request)
    return FactoryBridgeResult(action=action, request=request, plan=plan, knowledge_items=len(selected))


def autopilot_to_factory(
    actions: Iterable[AutopilotAction],
    knowledge_rows: Iterable[Mapping] = (),
) -> tuple[FactoryBridgeResult, ...]:
    rows = list(knowledge_rows)
    return tuple(action_to_factory(action, rows) for action in actions)
