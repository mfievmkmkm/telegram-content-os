from datetime import datetime
from zoneinfo import ZoneInfo

from content_os.database import Database


def test_future_schedule_can_be_returned_to_review(tmp_path):
    db=Database(str(tmp_path/"content.db"),ZoneInfo("UTC")); db.init()
    draft_id=db.save_draft("liga","разбор","Текст",4)
    db.update(draft_id,status="scheduled",scheduled_at="2099-01-01T12:00:00+00:00")
    assert [row["id"] for row in db.future_scheduled(datetime.now(ZoneInfo("UTC")).isoformat())]==[draft_id]
    db.update(draft_id,status="review",scheduled_at=None)
    draft=db.draft(draft_id)
    assert draft["status"]=="review"
    assert draft["scheduled_at"] is None
