from content_os.football_challenge_runtime import _select, _text


def test_challenge_runtime_renders_metric_and_proof():
    challenge = _select("scan_before_receive")
    text = _text(challenge)
    assert challenge.title in text
    assert challenge.success_metric in text
    assert challenge.proof in text
    assert "Зачёт" in text


def test_known_challenge_key_is_stable():
    assert _select("keeper_set").key == "keeper_set"
