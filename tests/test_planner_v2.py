from content_os.planner_v2 import ContentCandidate, plan_day


def test_planner_rejects_weak_fact_sensitive_market_claim():
    plan=plan_day([
        ContentCandidate("gifts","market","Floor вырос на 80%",freshness=.9,relevance=.9,novelty=.8,evidence=.2,fact_sensitive=True),
        ContentCandidate("gifts","guide","Как проверять модель до покупки",freshness=.6,relevance=.9,novelty=.8,evidence=.9),
    ],per_project=2)
    assert any(item.kind=="guide" for item in plan.items)
    assert "Floor вырос на 80%" in plan.rejected


def test_planner_avoids_same_format_when_close_alternative_exists():
    rows=[
        ContentCandidate("liga","story","История игрока",freshness=.8,relevance=.9,novelty=.9,evidence=.8),
        ContentCandidate("liga","challenge","Челлендж первого касания",freshness=.75,relevance=.9,novelty=.9,evidence=.8),
    ]
    plan=plan_day(rows,recent_kinds={"liga":["story"]},per_project=1)
    assert plan.items[0].kind=="challenge"


def test_planner_never_needs_publish_permission():
    plan=plan_day([ContentCandidate("gifts","meme","Типичная ошибка при покупке",freshness=.8,relevance=.8,novelty=.8,evidence=.8)])
    assert plan.items
    assert not hasattr(plan,"publish")
