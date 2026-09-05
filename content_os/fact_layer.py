from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


NUMBER_PATTERN = re.compile(r"(?<!\w)(?:\d+(?:[.,]\d+)?\s?(?:%|TON|₽|\$|€)|\+\d+(?:[.,]\d+)?%)(?!\w)", re.I)


def normalize_number(value: str) -> str:
    return re.sub(r"\s+", "", value.upper().replace(",", "."))


def numeric_claims(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(normalize_number(item) for item in NUMBER_PATTERN.findall(text or "")))


@dataclass(frozen=True, slots=True)
class FactPack:
    source: str
    captured_at: str
    raw: str
    numbers: tuple[str, ...]
    confidence: str = "observed"

    @classmethod
    def create(cls, raw: str, source: str, confidence: str = "observed") -> "FactPack":
        return cls(source, datetime.now(timezone.utc).isoformat(), raw[:12000], numeric_claims(raw), confidence)


class FactStore:
    PREFIX = "v2:fact_pack:"

    def __init__(self, database): self.db = database

    def save(self, draft_id: int | str, pack: FactPack) -> None:
        self.db.set(self.PREFIX + str(draft_id), json.dumps(asdict(pack), ensure_ascii=False))

    def load(self, draft_id: int | str) -> FactPack | None:
        raw=self.db.get(self.PREFIX + str(draft_id))
        if not raw: return None
        try:
            value=json.loads(raw)
            return FactPack(source=str(value["source"]),captured_at=str(value["captured_at"]),raw=str(value["raw"]),
                            numbers=tuple(value.get("numbers") or ()),confidence=str(value.get("confidence") or "observed"))
        except (KeyError,TypeError,ValueError,json.JSONDecodeError): return None
