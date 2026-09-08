from content_os.autopilot_v2 import AutopilotAction
from content_os.factory_bridge import action_to_factory, autopilot_to_factory


def test_bridge_keeps_knowledge_separate_from_facts():
    action = AutopilotAction("gifts", "post", "Почему редкая модель не гарантирует спрос", {})
    knowledge = [{"text":"Хук должен быстро обозначить конфликт. Не обещай результат цифрами.","source_channel":"course"}]
    result = action_to_factory(action, knowledge, facts=["Подтверждённый факт"], source_refs=["source:1"])
    assert result.request.facts == ("Подтверждённый факт",)
    assert result.request.source_refs == ("source:1",)
    assert "Не добавляй цифры" in result.request.knowledge_context
    assert result.plan.stages[-1] == "review"


def test_shorts_action_gets_render_stages():
    action = AutopilotAction("liga", "shorts", "Сканирование поля до приёма", {})
    result = action_to_factory(action)
    assert result.request.format == "shorts"
    assert "short_script" in result.plan.stages
    assert result.plan.stages[-1] == "render"


def test_batch_bridge_preserves_review_only_contract():
    actions = [
        AutopilotAction("gifts", "post", "A", {}),
        AutopilotAction("liga", "meme", "B", {}),
    ]
    results = autopilot_to_factory(actions)
    assert len(results) == 2
    assert all("director" in item.plan.stages and "review" in item.plan.stages for item in results)
