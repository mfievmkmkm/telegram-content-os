from content_os.brand_cards import gift_card, use_gift_card

def test_gift_card_is_a_real_png():
    data=gift_card("💎 <b>Твой floor врёт тебе</b>\n\nЛиквидность важнее редкости","разбор_ошибки")
    assert data.startswith(b"\x89PNG")
    assert len(data)>10_000

def test_feed_mix_has_text_only_posts():
    assert [use_gift_card(x) for x in range(1,7)] == [True,True,False,True,True,False]

def test_card_style_changes_with_the_story():
    first=gift_card("Первый рыночный сигнал\n\nЛиквидность растёт","signal")
    second=gift_card("Совсем другой разбор\n\nFloor падает","analysis")
    assert first != second
