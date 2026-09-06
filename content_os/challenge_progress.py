from __future__ import annotations

import json
from datetime import date, timedelta


KEY = "v2:challenge_progress"


class ChallengeProgress:
    def __init__(self, db): self.db = db

    def records(self) -> list[dict]:
        try:
            value = json.loads(self.db.get(KEY) or "[]")
            return value if isinstance(value, list) else []
        except (TypeError, ValueError, json.JSONDecodeError): return []

    def complete(self, player: str, challenge_key: str, day: date | None = None) -> dict:
        day = day or date.today(); rows = self.records()
        if not any(x.get("player") == player and x.get("day") == day.isoformat() and x.get("challenge") == challenge_key for x in rows):
            rows.append({"player": player, "challenge": challenge_key, "day": day.isoformat()})
            self.db.set(KEY, json.dumps(rows[-500:], ensure_ascii=False))
        days = {date.fromisoformat(x["day"]) for x in rows if x.get("player") == player and x.get("day")}
        streak = 0; cursor = day
        while cursor in days: streak += 1; cursor -= timedelta(days=1)
        return {"completed": len([x for x in rows if x.get("player") == player]), "streak": streak, "day": day.isoformat()}
