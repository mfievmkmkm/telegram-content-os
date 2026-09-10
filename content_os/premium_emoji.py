from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


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

# One coherent adaptive family: it follows Telegram's light/dark theme instead
# of mixing unrelated colourful packs. Later packs only fill missing meanings;
# the first matching glyph wins, preserving a consistent visual language.
RECOMMENDED_PACKS = ("AdaptiveIcons", "AdaptiveLines", "AdaptivePremium")
BRAND_FALLBACKS = frozenset(
    {item.fallback.replace("\ufe0f", "") for item in CATALOG}
    | {
        "🎁", "🎬", "📲", "🤖", "✍", "🏠", "🛒", "📈", "📊", "💰",
        "✅", "❌", "⭐", "🚀", "🔒", "🛡", "💡", "🤝", "🎙",
    }
)


def custom_emoji_mapping(sticker_sets: Iterable[object]) -> dict[str, str]:
    """Extract a restrained brand dictionary from Telegram custom-emoji sets."""
    result: dict[str, str] = {}
    for sticker_set in sticker_sets:
        for sticker in getattr(sticker_set, "stickers", ()) or ():
            fallback = str(getattr(sticker, "emoji", "") or "").replace("\ufe0f", "")
            emoji_id = str(getattr(sticker, "custom_emoji_id", "") or "")
            if fallback in BRAND_FALLBACKS and emoji_id.isdigit():
                result.setdefault(fallback, emoji_id)
    return result


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
