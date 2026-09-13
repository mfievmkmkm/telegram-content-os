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

# A fixed pair per editorial vertical gives every post the same visual rhythm.
# The glyphs are only fallbacks: publication replaces them with custom-emoji
# document IDs from one adaptive Telegram pack.
BRAND_ANCHORS = {
    "liga": ("⚡", "🎯"),
    "gifts": ("💎", "🧠"),
}

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
    """Return a stable brand pair first, then at most one semantic accent."""
    value = str(text or "").lower()
    cap = max(0, min(limit, 3))
    chosen = [
        fallback
        for fallback in BRAND_ANCHORS.get(channel, ())
        if fallback in text and str(available.get(fallback, "")).isdigit()
    ][:cap]
    ranked = []
    for index, item in enumerate(CATALOG):
        if channel not in item.channels or item.fallback not in available:
            continue
        score = sum(term in value for term in item.terms) * 10 + (2 if item.energy == "high" else 0) - index / 100
        if score > 0:
            ranked.append((score, item.fallback))
    ranked.sort(reverse=True)
    for _, fallback in ranked:
        if fallback in text and fallback not in chosen and len(chosen) < cap:
            chosen.append(fallback)
    # Old reviewed drafts may contain a valid non-anchor glyph. Keep it custom,
    # but never exceed the restrained brand limit.
    for fallback in available:
        if fallback in text and fallback not in chosen and len(chosen) < cap:
            chosen.append(fallback)
    return {fallback: available[fallback] for fallback in chosen if str(available[fallback]).isdigit()}


def missing_brand_anchors(channel: str, available: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        fallback
        for fallback in BRAND_ANCHORS.get(channel, ())
        if not str(available.get(fallback, "")).isdigit()
    )
