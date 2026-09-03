from content_os.gifts_data import GiftsDataDesk

def test_editorial_facts_uses_real_values():
    snapshot={"gift_asset":{"greed":{"A":{"score":61.25}},"health":{"A":{"health_index":8.9,"total_liquidity":3}}},"own_signals":[],"errors":[]}
    facts=GiftsDataDesk.editorial_facts(snapshot)
    assert "A 61.2" in facts
    assert "A 8.9" in facts


def test_editorial_facts_understands_wrapped_prices_and_volumes():
    snapshot={"gift_asset":{
      "prices":{"data":{"collection_floors":{"Plush":{"portals":4.2,"mrkt":3.9,"last_update":"now"}}}},
      "volumes":{"portals":{"Plush":{"hour_sales":12}}}},"own_signals":[],"errors":[]}
    facts=GiftsDataDesk.editorial_facts(snapshot)
    assert "Plush — 3.9 TON (mrkt)" in facts
    assert "Plush — 12 (portals)" in facts


def test_official_catalog_is_a_useful_fallback():
    snapshot={"gift_asset":{},"own_signals":[],"errors":["market down"],"telegram_catalog":[
      {"id":"gift-a","star_count":500,"total_count":1000,"remaining_count":25,"is_premium":True,"unique_gift_variant_count":120}
    ]}
    facts=GiftsDataDesk.editorial_facts(snapshot)
    assert "1 подарков" in facts
    assert "осталось 25/1000 (2.5%)" in facts
    assert "500 Stars" in facts
