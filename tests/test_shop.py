from content_os.shop import OFFERS, category_keyboard, offer_keyboard, shop_nav, storefront


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


def test_shop_navigation_never_traps_customer():
    callbacks={button.callback_data for row in offer_keyboard("liga_episode").inline_keyboard for button in row if button.callback_data}
    assert {"shop:home","shop:category:liga"} <= callbacks
    nav={button.callback_data for row in shop_nav("shop:offer:liga_episode").inline_keyboard for button in row}
    assert nav=={"shop:offer:liga_episode","shop:home"}


def test_gifts_subscription_is_a_direct_external_link():
    button=storefront("vsdvscbot").inline_keyboard[2][0]
    assert button.callback_data is None
    assert button.url=="https://t.me/vsdvscbot?start=shop"
