from content_os.gifts_data import GiftsDataDesk

def test_editorial_facts_uses_real_values():
    snapshot={"gift_asset":{"greed":{"A":{"score":61.25}},"health":{"A":{"health_index":8.9,"total_liquidity":3}}},"own_signals":[],"errors":[]}
    facts=GiftsDataDesk.editorial_facts(snapshot)
    assert "A 61.2" in facts
    assert "A 8.9" in facts
