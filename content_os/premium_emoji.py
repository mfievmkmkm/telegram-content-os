from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmojiIntent:
    fallback: str
    meaning: str
    channels: tuple[str, ...]
    terms: tuple[str, ...]
    energy: str = "medium"


CATALOG = (
    EmojiIntent("⚠️", "warning", ("gifts", "liga"), ("опас", "ошиб", "не делай", "осторож", "скам"), "high"),
    EmojiIntent("🔥", "heat", ("gifts", "liga"), ("горяч", "памп", "рывок", "жёст", "взорвал"), "high"),
    EmojiIntent("👀", "attention", ("gifts", "liga"), ("смотри", "заметь", "пропуска", "деталь", "увид")),
    EmojiIntent("🧠", "analysis", ("gifts", "liga"), ("анализ", "решен", "понима", "тактик", "контекст")),
    EmojiIntent("🎯", "precision", ("gifts", "liga"), ("точн", "цель", "удар", "выбор", "план")),
    EmojiIntent("💎", "rarity", ("gifts",), ("редк", "модел", "атрибут", "коллекц")),
    EmojiIntent("📉", "market", ("gifts",), ("floor", "цена", "рынок", "ликвид", "спрос")),
    EmojiIntent("⚽", "football", ("liga",), ("мяч", "матч", "футбол", "поле", "игрок")),
    EmojiIntent("⚡", "speed", ("liga",), ("скорост", "рывок", "реакц", "быстр", "темп"), "high"),
)


def semantic_custom_emojis(text: str, channel: str, available: dict[str, str], limit: int = 3) -> dict[str, str]:
    """Return only meaningful, configured emoji IDs; never break plain fallback."""
    value = str(text or "").lower()
    ranked = []
    for index, item in enumerate(CATALOG):
        if channel not in item.channels or item.fallback not in available:
            continue
        score = sum(term in value for term in item.terms) * 10 + (2 if item.energy == "high" else 0) - index / 100
        if score > 0:
            ranked.append((score, item.fallback))
    ranked.sort(reverse=True)
    chosen = [fallback for _, fallback in ranked[: max(0, min(limit, 3))]]
    # The first brand anchor remains available when the text already contains it.
    for fallback in available:
        if fallback in text and fallback not in chosen and len(chosen) < min(limit, 3):
            chosen.append(fallback)
    return {fallback: available[fallback] for fallback in chosen if str(available[fallback]).isdigit()}
