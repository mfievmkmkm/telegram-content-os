from datetime import date

from content_os.football_challenges import daily_challenge, progress_score
from content_os.meme_engine import build_meme


def test_gifts_meme_avoids_physical_gift_visuals_and_numbers():
    meme = build_meme("gifts", "Floor вырос на 83% и цена 12.5 TON")
    assert "83" not in meme.setup
    assert "12.5" not in meme.setup
    assert "physical gift boxes" in meme.visual_prompt
    assert meme.fingerprint()


def test_meme_rotates_away_from_recent_fingerprint():
    first = build_meme("liga", "после ошибки команда поплыла")
    second = build_meme("liga", "после ошибки команда поплыла", [first.fingerprint()])
    assert first.fingerprint() != second.fingerprint()


def test_daily_challenge_is_stable_for_same_player_and_day():
    day = date(2026, 9, 5)
    assert daily_challenge(7, "field", day) == daily_challenge(7, "field", day)


def test_goalkeeper_gets_no_field_only_challenge():
    challenge = daily_challenge(9, "goalkeeper", date(2026, 9, 5))
    assert challenge.position in {"all", "goalkeeper"}


def test_progress_score_is_bounded():
    assert progress_score(8, 10) == 80
    assert progress_score(20, 10) == 100
    assert progress_score(1, 0) == 0
