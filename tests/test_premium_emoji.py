from content_os.premium_emoji import semantic_custom_emojis


def test_semantic_custom_emoji_is_limited_and_channel_aware():
    available = {"⚠️": "1", "🔥": "2", "💎": "3", "📉": "4", "⚽": "5"}
    result = semantic_custom_emojis("⚠️ Редкая модель падает: floor и ликвидность важнее 🔥", "gifts", available)
    assert 1 <= len(result) <= 3
    assert "⚽" not in result
    assert all(value.isdigit() for value in result.values())


def test_invalid_ids_are_ignored_without_breaking_fallback():
    assert semantic_custom_emojis("⚠️ Ошибка", "liga", {"⚠️": "broken"}) == {}
