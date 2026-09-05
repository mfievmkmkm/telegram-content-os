from content_os.campaigns import CampaignRef
from content_os.growth.cta import telegram_deep_link
from content_os.growth.insights import best_observed, rank_dimension


def test_tracked_cta_uses_compact_start_payload():
    ref = CampaignRef("gifts", 184, "shorts", "tracker")
    cta = telegram_deep_link("@vsdvscbot", ref)
    assert cta.url.startswith("https://t.me/vsdvscbot?start=c_g_184_s_tracker")
    assert len(cta.token) <= 64
    assert cta.source == "gifts:shorts:184"


def test_growth_insights_are_descriptive_and_sample_aware():
    rows = [
        {"hook": "loss", "bot_starts": 5},
        {"hook": "loss", "bot_starts": 7},
        {"hook": "guide", "bot_starts": 4},
        {"hook": "guide", "bot_starts": 4},
        {"hook": "shock", "bot_starts": 99},
    ]
    ranked = rank_dimension(rows, "hook", "bot_starts", minimum_samples=2)
    assert [item.value for item in ranked] == ["loss", "guide"]
    assert ranked[0].confidence == "low"
    assert best_observed(rows, "hook", "bot_starts", 2).value == "loss"
