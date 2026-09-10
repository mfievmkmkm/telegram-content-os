from types import SimpleNamespace

from content_os.premium_emoji import custom_emoji_mapping, semantic_custom_emojis


def test_semantic_custom_emoji_is_limited_and_channel_aware():
    available = {"⚠️": "1", "🔥": "2", "💎": "3", "📉": "4", "⚽": "5"}
    result = semantic_custom_emojis("⚠️ Редкая модель падает: floor и ликвидность важнее 🔥", "gifts", available)
    assert 1 <= len(result) <= 3
    assert "⚽" not in result
    assert all(value.isdigit() for value in result.values())


def test_invalid_ids_are_ignored_without_breaking_fallback():
    assert semantic_custom_emojis("⚠️ Ошибка", "liga", {"⚠️": "broken"}) == {}


def test_curated_pack_mapping_keeps_brand_symbols_and_first_style():
    first = SimpleNamespace(stickers=[
        SimpleNamespace(emoji="💎", custom_emoji_id="101"),
        SimpleNamespace(emoji="😺", custom_emoji_id="102"),
    ])
    filler = SimpleNamespace(stickers=[
        SimpleNamespace(emoji="💎", custom_emoji_id="999"),
        SimpleNamespace(emoji="📉", custom_emoji_id="103"),
    ])
    assert custom_emoji_mapping((first, filler)) == {"💎": "101", "📉": "103"}


def test_curated_pack_mapping_supports_editor_and_shop_ui():
    ui_pack = SimpleNamespace(stickers=[
        SimpleNamespace(emoji="🎬", custom_emoji_id="201"),
        SimpleNamespace(emoji="📲", custom_emoji_id="202"),
        SimpleNamespace(emoji="🤖", custom_emoji_id="203"),
        SimpleNamespace(emoji="🏠", custom_emoji_id="204"),
        SimpleNamespace(emoji="🛒", custom_emoji_id="205"),
    ])
    assert custom_emoji_mapping((ui_pack,)) == {
        "🎬": "201", "📲": "202", "🤖": "203", "🏠": "204", "🛒": "205",
    }
