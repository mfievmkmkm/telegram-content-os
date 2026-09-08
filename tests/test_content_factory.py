import pytest

from content_os.content_factory import FactoryRequest, build_factory_plan


def test_gifts_factory_refuses_fake_analytics_by_rule():
    plan = build_factory_plan(FactoryRequest(project="gifts", topic="редкие модели"))
    assert any("fake analytics" in rule for rule in plan.prompt_rules)
    assert plan.stages[-1] == "review"


def test_shorts_extends_reviewed_pipeline_into_rendering():
    plan = build_factory_plan(FactoryRequest(project="liga", topic="первое касание", format="shorts"))
    assert plan.stages[:6] == ("research", "knowledge", "draft", "director", "visual", "review")
    assert plan.stages[-4:] == ("short_script", "voice", "scenes", "render")


def test_factory_preserves_attribution_and_fact_counts():
    plan = build_factory_plan(FactoryRequest(project="services", topic="контент", facts=("fact",), source_refs=("src",), campaign_token="abc"))
    assert plan.metadata["campaign_token"] == "abc"
    assert plan.metadata["fact_count"] == "1"


def test_factory_rejects_unknown_project():
    with pytest.raises(ValueError):
        build_factory_plan(FactoryRequest(project="unknown", topic="x"))
