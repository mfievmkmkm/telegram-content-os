from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class FactoryRequest:
    project: str
    topic: str
    format: str = "post"
    objective: str = "engagement"
    facts: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    knowledge_context: str = ""
    campaign_token: str = ""


@dataclass(frozen=True)
class FactoryPlan:
    project: str
    topic: str
    format: str
    stages: tuple[str, ...]
    prompt_rules: tuple[str, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)


def build_factory_plan(request: FactoryRequest) -> FactoryPlan:
    project = request.project.strip().lower()
    if project not in {"gifts", "liga", "services"}:
        raise ValueError("unsupported project")
    if not request.topic.strip():
        raise ValueError("topic is required")
    rules = [
        "strong hook in first 1-3 seconds/lines",
        "do not invent facts, prices, statistics or market movement",
        "knowledge context is guidance, never factual evidence",
        "creative director must approve before scheduling or publishing",
        "preserve source references for fact-sensitive claims",
    ]
    if project == "gifts":
        rules.append("without reliable market facts, use education/psychology/safety/meme angle instead of fake analytics")
    if project == "liga":
        rules.append("prefer actionable football observation, drill or decision over generic motivation")
    stages = ("research", "knowledge", "draft", "director", "visual", "review")
    if request.format in {"short", "shorts", "reel"}:
        stages += ("short_script", "voice", "scenes", "render")
    metadata = {
        "objective": request.objective,
        "campaign_token": request.campaign_token,
        "fact_count": str(len(request.facts)),
        "source_count": str(len(request.source_refs)),
    }
    return FactoryPlan(project, request.topic.strip(), request.format, stages, tuple(rules), metadata)
