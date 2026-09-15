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

# These are fallback priorities, not a compulsory signature. The renderer picks
# two relevant signs that actually exist in the selected custom-emoji family.
BRAND_ANCHORS = {
    "liga": ("⚽", "⚡", "🎯", "🧠", "🔥", "👀"),
    "gifts": ("💡", "🧠", "🎯", "💎", "👀", "🔥", "📉"),
}

# One coherent adaptive family: it follows Telegram's light/dark theme instead
# of mixing unrelated colourful packs. Later packs only fill missing meanings;
# the first matching glyph wins, preserving a consistent visual language.
EMOJI_THEMES = {
    "editorial": {
        "title": "Editorial Mono",
        "description": "Спокойные adaptive-иконки под светлую и тёмную тему",
        "packs": ("AdaptiveIcons", "AdaptiveLines", "AdaptivePremium"),
    },
    "character": {
        "title": "Character Accent",
        "description": "Более живой акцент для мемов и историй",
        "packs": ("LiterallyMineEmojis",),
    },
}
RECOMMENDED_PACKS = tuple(dict.fromkeys(
    name for theme in EMOJI_THEMES.values() for name in theme["packs"]
))
BRAND_FALLBACKS = frozenset(
    {item.fallback.replace("\ufe0f", "") for item in CATALOG}
    | {
        "🎁", "🎬", "📲", "🤖", "✍", "🏠", "🛒", "📈", "📊", "💰",
        "✅", "❌", "⭐", "🚀", "🔒", "🛡", "💡", "🤝", "🎙", "⚙",
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


def semantic_anchors(text: str, channel: str, available: dict[str, str], limit: int = 2) -> tuple[str, ...]:
    """Choose restrained, topic-aware accents from one installed family."""
    normalized = {
        str(key).replace("\ufe0f", ""): str(value)
        for key, value in (available or {}).items()
        if str(value).isdigit()
    }
    value = str(text or "").lower()
    ranked: list[tuple[float, str]] = []
    for index, item in enumerate(CATALOG):
        fallback = item.fallback.replace("\ufe0f", "")
        if channel not in item.channels or fallback not in normalized:
            continue
        score = sum(term in value for term in item.terms) * 10
        score += 1 if fallback in BRAND_ANCHORS.get(channel, ()) else 0
        score -= index / 100
        ranked.append((score, fallback))
    ranked.sort(reverse=True)
    chosen = [fallback for _, fallback in ranked if fallback not in ()][:max(0, limit)]
    for fallback in BRAND_ANCHORS.get(channel, ()):
        fallback = fallback.replace("\ufe0f", "")
        if fallback in normalized and fallback not in chosen and len(chosen) < limit:
            chosen.append(fallback)
    for fallback in normalized:
        if fallback not in chosen and len(chosen) < limit:
            chosen.append(fallback)
    return tuple(chosen)


def semantic_custom_emojis(text: str, channel: str, available: dict[str, str], limit: int = 3) -> dict[str, str]:
    """Return only topic-aware glyphs that occur in the rendered post."""
    value = str(text or "").lower()
    cap = max(0, min(limit, 3))
    normalized = {str(key).replace("\ufe0f", ""): str(item) for key, item in available.items()}
    chosen = [fallback for fallback in semantic_anchors(text, channel, normalized, cap) if fallback in text]
    ranked = []
    for index, item in enumerate(CATALOG):
        fallback=item.fallback.replace("\ufe0f","")
        if channel not in item.channels or fallback not in normalized:
            continue
        score = sum(term in value for term in item.terms) * 10 + (2 if item.energy == "high" else 0) - index / 100
        if score > 0:
            ranked.append((score, fallback))
    ranked.sort(reverse=True)
    for _, fallback in ranked:
        if fallback in text and fallback not in chosen and len(chosen) < cap:
            chosen.append(fallback)
    # Old reviewed drafts may contain a valid non-anchor glyph. Keep it custom,
    # but never exceed the restrained brand limit.
    for fallback in normalized:
        if fallback in text and fallback not in chosen and len(chosen) < cap:
            chosen.append(fallback)
    return {fallback: normalized[fallback] for fallback in chosen if str(normalized[fallback]).isdigit()}


def missing_brand_anchors(channel: str, available: dict[str, str]) -> tuple[str, ...]:
    count=len(semantic_anchors("",channel,available,2))
    return tuple("◇" for _ in range(max(0,2-count)))
