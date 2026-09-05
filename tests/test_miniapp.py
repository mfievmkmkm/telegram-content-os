import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pytest

from content_os.database import Database
from content_os.miniapp_runtime import dashboard_snapshot, validate_init_data


def signed_init_data(token="token", username="skillell", age=0):
    values = {
        "auth_date": str(int(time.time()) - age),
        "query_id": "AAE-test",
        "user": json.dumps({"id": 7, "username": username}, separators=(",", ":")),
    }
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_validate_init_data_accepts_telegram_signature():
    assert validate_init_data(signed_init_data(), "token")["username"] == "skillell"


def test_validate_init_data_rejects_tampering_and_expiry():
    with pytest.raises(ValueError):
        validate_init_data(signed_init_data().replace("skillell", "intruder"), "token")
    with pytest.raises(ValueError):
        validate_init_data(signed_init_data(age=90_000), "token")


def test_dashboard_snapshot_uses_shared_content_entities(tmp_path):
    db = Database(str(tmp_path / "content.db"), ZoneInfo("UTC"))
    db.init()
    draft_id = db.save_draft("gifts", "разбор_ошибки", "Не смотри только на floor", 88)
    snapshot = dashboard_snapshot(db)
    assert snapshot["counts"]["review"] == 1
    assert snapshot["drafts"][0]["id"] == draft_id
    assert set(snapshot) >= {"drafts", "calendar", "analytics", "players", "orders"}
