from shorts_service.subtitles import ass_subtitles_v2


def test_partial_tts_alignment_never_drops_remaining_subtitles():
    script="первое второе третье четвертое пятое шестое седьмое восьмое"
    alignment={
        "characters":list("первое второе "),
        "character_start_times_seconds":[i*.04 for i in range(14)],
        "character_end_times_seconds":[(i+1)*.04 for i in range(14)],
    }
    result=ass_subtitles_v2(script,4.0,"clean",alignment)
    assert "седьмое восьмое" in result
