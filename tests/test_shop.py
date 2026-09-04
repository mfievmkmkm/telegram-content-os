from content_os.shop import OFFERS, category_keyboard, offer_keyboard, storefront


def test_catalog_has_three_real_directions():
    assert {"liga_episode", "liga_match", "ai_short", "content_system"} <= set(OFFERS)
    assert {offer.category for offer in OFFERS.values()} == {"liga", "services"}
    assert all(offer.price and offer.description and offer.result and offer.turnaround for offer in OFFERS.values())


def test_storefront_and_offer_have_action_buttons():
    assert len(storefront().inline_keyboard) == 4
    assert storefront("my_gifts_bot").inline_keyboard[2][0].url == "https://t.me/my_gifts_bot?start=shop"
    assert category_keyboard("liga").inline_keyboard[0][0].callback_data.startswith("shop:offer:")
    assert len(category_keyboard("services").inline_keyboard) == 6
    assert offer_keyboard("ai_short").inline_keyboard[0][0].callback_data == "shop:order:ai_short"
