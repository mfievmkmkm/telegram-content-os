"""Versioned Remix bundles in the shared SQLite/Supabase settings store."""
from dataclasses import asdict
import json
from uuid import uuid4


class RemixStore:
    PREFIX = "v2:remix:bundle:"

    def __init__(self, db):
        self.db = db

    def create(self, source, bundle):
        bundle_id = uuid4().hex[:16]
        value = {"version": 1, "source_id": int(source["id"]), "channel": source["channel_key"],
                 "formats": asdict(bundle)}
        self.db.set(self.PREFIX + bundle_id, json.dumps(value, ensure_ascii=False))
        return bundle_id

    def load(self, bundle_id):
        try:
            value = json.loads(self.db.get(self.PREFIX + bundle_id) or "null")
            if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("formats"), dict):
                return None
            if value.get("channel") not in {"gifts", "liga"} or not isinstance(value.get("source_id"), int):
                return None
            return value
        except (ValueError, TypeError):
            return None

    def result(self, bundle_id, kind):
        raw = self.db.get(f"{self.PREFIX}{bundle_id}:result:{kind}")
        return int(raw) if raw and str(raw).isdigit() else None

    def remember(self, bundle_id, kind, result_id):
        self.db.set(f"{self.PREFIX}{bundle_id}:result:{kind}", str(result_id))


def save_poll(db, draft_id, question, options):
    validate_poll(question, options)
    db.set(f"v2:poll:{draft_id}", json.dumps({"question": question, "options": options}, ensure_ascii=False))


def validate_poll(question, options):
    if not isinstance(question, str) or not 1 <= len(question) <= 250:
        raise ValueError("Вопрос опроса должен содержать 1–250 знаков")
    if (not isinstance(options, (list, tuple)) or not 2 <= len(options) <= 4
            or any(not isinstance(x, str) or not x.strip() or len(x) > 100 for x in options)
            or len({x.strip().casefold() for x in options}) != len(options)):
        raise ValueError("Опрос должен содержать 2–4 разных варианта до 100 знаков")


def load_poll(db, draft_id):
    try:
        data = json.loads(db.get(f"v2:poll:{draft_id}") or "null")
        if not isinstance(data, dict):
            raise ValueError("Опрос не найден; создай его из Remix заново")
        validate_poll(data.get("question"), data.get("options"))
        return data
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Данные опроса повреждены; создай его из Remix заново") from exc
