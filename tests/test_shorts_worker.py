from shorts_service.core import alignment_chunks, ass_subtitles, caption_chunks, clean_script, unique_terms


def test_clean_script_removes_visual_emojis_from_voice():
    value=clean_script("💎 Кит продал 10 ⭐ 🔥")
    assert "💎" not in value and "🔥" not in value and "⭐" not in value
    assert "10 звёзд" in value


def test_script_is_tight_and_subtitles_are_short():
    script=clean_script("Ты купил вершину — и молчишь...\nТеперь смотри на ликвидность")
    assert "—" not in script and "..." not in script and "\n" not in script
    assert all(len(chunk.split())<=7 for chunk in caption_chunks(script))
    ass=ass_subtitles(script,12)
    assert "PlayResY: 1280" in ass and "Dialogue:" in ass
    assert all(len(chunk.split())<=4 for chunk in caption_chunks(script))


def test_stock_terms_are_safe_and_unique():
    terms=unique_terms({"video_terms":["football training","Football Training","TON $$$ chart","","gift"]})
    assert terms==["football training","TON  chart","gift"]


def test_alignment_chunks_follow_real_voice_timing():
    text="Смотри рынок сейчас"
    alignment={"characters":list(text),
      "character_start_times_seconds":[i*.05 for i in range(len(text))],
      "character_end_times_seconds":[(i+1)*.05 for i in range(len(text))]}
    chunks=alignment_chunks(alignment,2)
    assert chunks[0][0]=="Смотри рынок"
    assert chunks[1][0]=="сейчас"
    assert chunks[0][1]==0
    assert chunks[-1][2]>.8


def test_subtitles_have_outline_without_opaque_rectangles():
    ass=ass_subtitles("Проверяй факты до покупки",4)
    assert ",1,4,2,2," in ass
    assert ",3,3,1,2," not in ass
