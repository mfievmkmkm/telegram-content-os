from datetime import date

from content_os.autopilot_v2 import build_autopilot_plan
from content_os.meme_engine import MemeConcept
from content_os.planner_v2 import ContentCandidate


def candidate(project: str, kind: str, topic: str) -> ContentCandidate:
    return ContentCandidate(project, kind, topic, freshness=.9, relevance=.9, novelty=.9, evidence=.9)


def test_autopilot_never_marks_plan_as_unreviewed_publishable():
    plan = build_autopilot_plan([candidate("gifts", "post", "Редкая модель против floor")])
    assert plan.publishable_without_review is False
    assert all(action.requires_review for action in plan.actions)


def test_autopilot_routes_meme_to_meme_engine():
    plan = build_autopilot_plan([candidate("gifts", "meme", "листинг забрали за секунды")])
    assert isinstance(plan.actions[0].payload, MemeConcept)
    assert plan.actions[0].kind == "meme"


def test_autopilot_routes_liga_challenge_to_challenge_engine():
    plan = build_autopilot_plan([candidate("liga", "challenge", "первый приём")], day=date(2026, 9, 5))
    action = plan.actions[0]
    assert action.kind == "challenge"
    assert getattr(action.payload, "success_metric")


def test_regular_content_is_sent_to_content_factory_not_fake_generated():
    plan = build_autopilot_plan([candidate("liga", "short", "почему игрок исчезает после ошибки")])
    payload = plan.actions[0].payload
    assert payload["next_stage"] == "content_factory"
    assert payload["topic"] == "почему игрок исчезает после ошибки"
