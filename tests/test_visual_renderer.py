from content_os.visual_renderer import fresh_page_offset, layout_key, preview_variants, render_card


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


def test_preview_supports_non_repeating_pages():
    first = preview_variants("liga", "Первое касание решает эпизод", "обучение", 3, 0)
    more = preview_variants("liga", "Первое касание решает эпизод", "обучение", 3, 3)
    assert len(first) == len(more) == 3
    assert not set(first) & set(more)


def test_visual_library_has_eight_real_art_directions():
    text = "Ты купил красивую модель, но забыл проверить ликвидность"
    cards = [render_card("gifts", text, "разбор_ошибки", index) for index in range(8)]
    assert len(set(cards)) == 8
    assert [layout_key(index) for index in range(8)] == [
        "cinematic", "photo_split", "number_poster", "dashboard",
        "chat_meme", "dossier", "editorial", "spotlight",
    ]


def test_visual_director_opens_a_fresh_page():
    assert fresh_page_offset([]) == 0
    assert fresh_page_offset(["cinematic", "photo_split", "number_poster"]) == 3
    assert fresh_page_offset(["dashboard", "chat_meme", "dossier"]) in {0, 6}
