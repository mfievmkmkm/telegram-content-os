import io

from PIL import Image, ImageDraw

from content_os.brand_cards import LIGA_SCENES, SCENES, _cinematic, _pick_liga_scene, _wrap_pixels, font, gift_card, liga_card, use_gift_card

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
    assert _pick_liga_scene("Почему вратарь опоздал с сейвом",1) in {"goalkeeper.webp","keeper_flight.webp"}
    assert _pick_liga_scene("Как вернуть место в составе после замены",1) in {"golden_bench.webp","empty_bench.webp"}
    assert _pick_liga_scene("Упражнение на скорость и конусы",1) in {"night_training.webp","sprint_rain.webp"}
    assert _pick_liga_scene("Тактический разбор эпизода",1) in {"tactics_lab.webp","coach_hologram.webp"}
    assert _pick_liga_scene("Победа в единоборстве",1) == "duel_fire.webp"
    assert _pick_liga_scene("Как поставить удар",1) == "neon_strike.webp"

def test_meme_cards_use_distinct_editorial_layouts():
    gift=gift_card("Когда купил вершину и назвал это стратегией","мем")
    liga=liga_card("Когда тренер сказал разминаться на 89-й","мем")
    assert gift.startswith(b"\x89PNG") and liga.startswith(b"\x89PNG")
    assert gift != liga

def test_pixel_wrapper_never_overflows_cyrillic_card_width():
    draw=ImageDraw.Draw(Image.new("RGB",(1080,1080))); current_font=font(58)
    lines=_wrap_pixels(draw,"Ты открылся правильно, но мяч всё равно снова ушёл назад",current_font,500)
    assert len(lines)>1
    assert all(draw.textbbox((0,0),line,font=current_font)[2]<=500 for line in lines)
