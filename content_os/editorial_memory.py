from __future__ import annotations

import json

from .content_fingerprint import ContentFingerprint


class EditorialMemory:
    """Compact JSON memory stored in the existing settings KV table.

    This deliberately avoids a schema migration during Milestone A. Once analytics
    starts querying fingerprints at scale, it can move to dedicated tables.
    """

    def __init__(self, database, limit: int = 50):
        self.db = database
        self.limit = max(20, min(int(limit), 100))

    def fingerprints(self, channel: str) -> list[tuple[ContentFingerprint, str]]:
        rows = self._json(f"v2:fingerprints:{channel}", [])
        result = []
        for row in rows:
            try:
                fp = ContentFingerprint(**row["fingerprint"])
                result.append((fp, str(row.get("text") or "")))
            except (KeyError, TypeError, ValueError):
                continue
        return result

    def remember_content(self, channel: str, fingerprint: ContentFingerprint, text: str, draft_id=None) -> None:
        key = f"v2:fingerprints:{channel}"
        rows = self._json(key, [])
        item = {"draft_id": draft_id, "fingerprint": fingerprint.to_dict(), "text": text[:5000]}
        rows = [row for row in rows if row.get("draft_id") != draft_id] if draft_id is not None else rows
        rows.append(item)
        self._save(key, rows[-self.limit:])

    def recent_visuals(self, channel: str) -> list[str]:
        return [str(x) for x in self._json(f"v2:visuals:{channel}", []) if x]

    def remember_visual(self, channel: str, key_value: str) -> None:
        key = f"v2:visuals:{channel}"
        rows = self.recent_visuals(channel)
        rows.append(str(key_value))
        self._save(key, rows[-12:])

    def selected_variant(self, draft_id: int | str) -> int | None:
        value = self.db.get(f"v2:visual_variant:{draft_id}")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def select_variant(self, draft_id: int | str, variant: int) -> None:
        self.db.set(f"v2:visual_variant:{draft_id}", str(max(0, min(int(variant), 2))))

    def _json(self, key: str, fallback):
        raw = self.db.get(key)
        if not raw:
            return fallback
        try:
            value = json.loads(raw)
            return value if isinstance(value, type(fallback)) else fallback
        except (TypeError, ValueError, json.JSONDecodeError):
            return fallback

    def _save(self, key: str, value) -> None:
        self.db.set(key, json.dumps(value, ensure_ascii=False))
