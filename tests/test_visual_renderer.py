from content_os.visual_renderer import preview_variants, render_card


def test_visual_variants_are_stable_and_distinct():
    text = "Ты смотришь только на floor\nА редкая модель уже ушла ниже рынка"
    first = render_card("gifts", text, "разбор_ошибки", 0)
    same = render_card("gifts", text, "разбор_ошибки", 0)
    second = render_card("gifts", text, "разбор_ошибки", 1)
    assert first == same
    assert first != second
    assert first.startswith(b"\x89PNG")


def test_preview_is_capped_to_three():
    cards = preview_variants("liga", "Тренер убрал тебя не из-за одного паса\nРешение началось раньше", "история", 9)
    assert len(cards) == 3
    assert all(card.startswith(b"\x89PNG") for card in cards)
