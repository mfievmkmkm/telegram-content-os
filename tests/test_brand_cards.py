from content_os.brand_cards import gift_card

def test_gift_card_is_a_real_png():
    data=gift_card("💎 <b>Твой floor врёт тебе</b>\n\nЛиквидность важнее редкости","разбор_ошибки")
    assert data.startswith(b"\x89PNG")
    assert len(data)>10_000
