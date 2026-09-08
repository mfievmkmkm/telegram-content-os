from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable


@dataclass(frozen=True)
class MemeConcept:
    channel_key: str
    situation: str
    setup: str
    punchline: str
    visual_prompt: str
    cta: str = ""

    def fingerprint(self) -> str:
        raw = "|".join((self.channel_key, self.situation, self.setup, self.punchline))
        return hashlib.sha256(raw.lower().encode("utf-8")).hexdigest()[:16]


CHANNEL_RULES = {
    "gifts": {
        "situations": (
            "увидел листинг слишком поздно",
            "купил на эмоциях после пампа",
            "смотрел только floor и пропустил редкую модель",
            "открыл слишком много вкладок рынка",
        ),
        "visuals": (
            "Telegram collectible marketplace UI, price cards, fast reaction meme, no physical gift boxes",
            "digital collectible trader staring at market listings, interface-first composition",
            "rare model highlighted inside a collectible card, marketplace context, editorial meme",
        ),
    },
    "liga": {
        "situations": (
            "на тренировке всё получалось, в матче исчезло",
            "после одной ошибки решил, что матч закончен",
            "на 70-й минуте ноги закончились раньше идей",
            "тренер сказал сыграть проще, а ты включил финал ЛЧ",
        ),
        "visuals": (
            "amateur football touchline reaction meme, realistic training ground",
            "football player freeze-frame with tactical overlay, editorial sports meme",
            "bench reaction during an amateur football match, documentary sports frame",
        ),
    },
}


def _clean(text: str, limit: int = 120) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    return value[:limit].rstrip(" ,.;:-")


def build_meme(channel_key: str, source_text: str, recent_fingerprints: Iterable[str] = ()) -> MemeConcept:
    """Create a compact meme concept without inventing factual claims.

    The source text is only used as a semantic anchor. Numbers, prices and stats are
    deliberately excluded from generated copy; factual memes can be authored by the
    editor only when a fact pack is available.
    """
    rules = CHANNEL_RULES.get(channel_key, CHANNEL_RULES["liga"])
    anchor = _clean(re.sub(r"\b\d+(?:[.,]\d+)?%?\b", "", source_text), 70) or "когда реальность решила проверить план"
    recent = set(recent_fingerprints)

    for situation in rules["situations"]:
        for visual in rules["visuals"]:
            concept = MemeConcept(
                channel_key=channel_key,
                situation=situation,
                setup=f"Ты: «{anchor}»",
                punchline=f"Реальность: {situation}",
                visual_prompt=visual,
            )
            if concept.fingerprint() not in recent:
                return concept

    # Exhausted combinations are still deterministic, but the source anchor changes
    # the fingerprint so the caller can decide whether to publish or request a remix.
    situation = rules["situations"][0]
    return MemeConcept(channel_key, situation, f"Ты: «{anchor}»", f"Реальность: {situation}", rules["visuals"][0])
