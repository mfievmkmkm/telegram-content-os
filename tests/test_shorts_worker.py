from shorts_service.core import ass_subtitles, caption_chunks, clean_script, unique_terms


def test_script_is_tight_and_subtitles_are_short():
    script=clean_script("Ты купил вершину — и молчишь...\nТеперь смотри на ликвидность")
    assert "—" not in script and "..." not in script and "\n" not in script
    assert all(len(chunk.split())<=7 for chunk in caption_chunks(script))
    ass=ass_subtitles(script,12)
    assert "PlayResY: 1920" in ass and "Dialogue:" in ass


def test_stock_terms_are_safe_and_unique():
    terms=unique_terms({"video_terms":["football training","Football Training","TON $$$ chart","","gift"]})
    assert terms==["football training","TON  chart","gift"]
