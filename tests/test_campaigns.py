from content_os.campaigns import CampaignRef, campaign_source, parse_campaign


def test_campaign_token_roundtrip():
    ref = CampaignRef("gifts", 184, "shorts", "gift-audit", "sep26")
    token = ref.token()
    assert len(token) <= 64
    parsed = parse_campaign(token)
    assert parsed == ref
    assert campaign_source(parsed) == "gifts:shorts:184:gift-audit:sep26"


def test_campaign_token_supports_campaign_without_offer():
    ref = CampaignRef("liga", 7, "post", campaign="hookb")
    assert parse_campaign(ref.token()) == ref


def test_invalid_campaign_is_ignored():
    assert parse_campaign("service_gifts") is None
    assert parse_campaign("c_x_1_p") is None
