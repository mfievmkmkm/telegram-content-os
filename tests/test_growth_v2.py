from datetime import datetime, timedelta, timezone

import pytest

from content_os.growth.analytics_v2 import build_growth_summary
from content_os.growth.attribution import CampaignRef, build_funnel_summary, campaign_source
from content_os.growth.experiments import Experiment, ExperimentVariant, validate_experiment


def test_growth_summary_uses_real_time_windows():
    published = datetime(2026, 9, 5, 10, tzinfo=timezone.utc)
    rows = [
        {"captured_at": (published + timedelta(minutes=65)).isoformat(), "views": 100, "reactions": 10},
        {"captured_at": (published + timedelta(hours=6, minutes=10)).isoformat(), "views": 400, "reactions": 30},
        {"captured_at": (published + timedelta(hours=24, minutes=20)).isoformat(), "views": 900, "reactions": 60},
        {"captured_at": (published + timedelta(hours=48, minutes=15)).isoformat(), "views": 1200, "reactions": 80},
    ]
    summary = build_growth_summary(42, published, rows)
    assert set(summary.windows) == {1, 6, 24, 48}
    assert summary.windows[24].views == 900
    assert summary.latest.views == 1200


def test_growth_summary_does_not_fake_missing_window():
    published = datetime(2026, 9, 5, 10, tzinfo=timezone.utc)
    rows = [{"captured_at": (published + timedelta(hours=19)).isoformat(), "views": 700}]
    summary = build_growth_summary(42, published, rows)
    assert 24 not in summary.windows


def test_campaign_ref_uses_telegram_safe_token_and_real_shop_event_names():
    ref = CampaignRef(project="gifts", content_id=184, format_key="shorts", offer="tracker")
    token = ref.token()
    assert len(token) <= 64
    summary = build_funnel_summary([
        {"source": token, "event_type": "landing"},
        {"source": token, "event_type": "recommendation"},
        {"source": token, "event_type": "order_created"},
        {"source": token, "event_type": "paid", "revenue": 990},
        {"source": "other", "event_type": "sale", "revenue": 99999},
    ], campaign_source(ref))
    assert summary.visits == 1
    assert summary.leads == 1
    assert summary.orders == 1
    assert summary.sales == 1
    assert summary.revenue == 990


def test_experiment_allows_only_one_changed_variable():
    good = Experiment(
        hypothesis="loss hook converts better",
        primary_variable="hook",
        control=ExperimentVariant("A", {"hook": "guide", "format": "short"}),
        challenger=ExperimentVariant("B", {"hook": "loss", "format": "short"}),
        success_metric="bot_starts",
    )
    validate_experiment(good)

    bad = Experiment(
        hypothesis="too many changes",
        primary_variable="hook",
        control=ExperimentVariant("A", {"hook": "guide", "visual": "clean"}),
        challenger=ExperimentVariant("B", {"hook": "loss", "visual": "meme"}),
        success_metric="sales",
    )
    with pytest.raises(ValueError, match="exactly one"):
        validate_experiment(bad)
