from datetime import date
from zoneinfo import ZoneInfo

from content_os.challenge_progress import ChallengeProgress
from content_os.database import Database


def test_challenge_streak_counts_consecutive_days(tmp_path):
    db = Database(str(tmp_path / "content.db"), ZoneInfo("UTC")); db.init(); progress = ChallengeProgress(db)
    progress.complete("7", "scan", date(2026, 9, 5))
    result = progress.complete("7", "touch", date(2026, 9, 6))
    assert result == {"completed": 2, "streak": 2, "day": "2026-09-06"}
