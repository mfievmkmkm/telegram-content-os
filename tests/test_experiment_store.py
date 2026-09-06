from zoneinfo import ZoneInfo

from content_os.database import Database
from content_os.growth.experiment_store import ExperimentStore


def test_experiment_lifecycle_is_persistent(tmp_path):
    db = Database(str(tmp_path / "content.db"), ZoneInfo("UTC")); db.init(); store = ExperimentStore(db)
    row = store.create("gifts", "Конкретный hook сильнее", "hook", "question", "loss", "engagement_rate", (4,))
    store.add_sample(row["id"], "control", .10); store.add_sample(row["id"], "challenger", .13)
    store.add_sample(row["id"], "control", .11); result = store.add_sample(row["id"], "challenger", .14)
    assert result["status"] == "provisional_challenger"
    assert result["uplift_percent"] > 10
