from content_os.shop import OFFERS, category_keyboard, offer_keyboard, storefront


def test_catalog_has_three_real_directions():
    assert {"liga_episode", "gifts_audit", "content_pack"} <= set(OFFERS)
    assert all(offer.price and offer.description for offer in OFFERS.values())


def test_storefront_and_offer_have_action_buttons():
    assert len(storefront().inline_keyboard) == 3
    assert category_keyboard("liga").inline_keyboard[0][0].callback_data.startswith("shop:offer:")
    assert offer_keyboard("gifts_audit").inline_keyboard[0][0].callback_data == "shop:order:gifts_audit"
