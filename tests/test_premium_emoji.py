from types import SimpleNamespace

from content_os.premium_emoji import custom_emoji_mapping, semantic_anchors, semantic_custom_emojis


def test_semantic_custom_emoji_is_limited_and_channel_aware():
    available = {"⚠️": "1", "🔥": "2", "💎": "3", "📉": "4", "⚽": "5"}
    result = semantic_custom_emojis("⚠️ Редкая модель падает: floor и ликвидность важнее 🔥", "gifts", available)
    assert 1 <= len(result) <= 3
    assert "⚽" not in result
    assert all(value.isdigit() for value in result.values())


def test_invalid_ids_are_ignored_without_breaking_fallback():
    assert semantic_custom_emojis("⚠️ Ошибка", "liga", {"⚠️": "broken"}) == {}


def test_anchor_pair_changes_with_subject_but_stays_inside_one_pack():
    available={"🧠":"1","🎯":"2","💎":"3","📉":"4","🔥":"5"}
    market=semantic_anchors("Цена и ликвидность рынка","gifts",available)
    analysis=semantic_anchors("Решение и анализ бизнеса","gifts",available)
    assert market != analysis
    assert all(item in available for item in market+analysis)


def test_neutral_posts_rotate_instead_of_using_one_permanent_pair():
    available={item:str(index) for index,item in enumerate(("🧠","🎯","💎","📉","🔥","💡","🔍","🎨"),1)}
    pairs={semantic_anchors(f"Новая нейтральная тема {index}","gifts",available) for index in range(12)}
    assert len(pairs)>=4


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
