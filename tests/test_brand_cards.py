import io

from PIL import Image

from content_os.brand_cards import LIGA_SCENES, SCENES, _cinematic, _pick_liga_scene, gift_card, liga_card, use_gift_card

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

def test_all_cinematic_scenes_render_at_telegram_size():
    for index, (channel, scene) in enumerate([*(('gifts', x) for x in SCENES), *(("liga", x) for x in LIGA_SCENES)]):
        image=_cinematic(
            ["Очень длинный заголовок про ликвидность подарков и поведение рынка", "Короткое объяснение сигнала"],
            index,
            scene,
            channel,
        )
        buffer=io.BytesIO(); image.save(buffer,"PNG")
        rendered=Image.open(io.BytesIO(buffer.getvalue()))
        assert rendered.size == (1080,1080)

def test_liga_card_is_a_real_png():
    data=liga_card("Ты бежишь много. Но открываешься поздно\n\nРазбираем движение без мяча","разбор матча")
    assert data.startswith(b"\x89PNG")
    assert len(data)>10_000

def test_liga_scene_matches_subject():
    assert _pick_liga_scene("Почему вратарь опоздал с сейвом",1) == "goalkeeper.webp"
    assert _pick_liga_scene("Как вернуть место в составе после замены",1) == "golden_bench.webp"
    assert _pick_liga_scene("Упражнение на дриблинг",1) == "night_training.webp"
    assert _pick_liga_scene("Тактический разбор эпизода",1) == "tactics_lab.webp"
