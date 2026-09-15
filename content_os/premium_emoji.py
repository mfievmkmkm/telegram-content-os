from __future__ import annotations

import hashlib
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
    EmojiIntent("🚨", "alert", ("gifts", "liga"), ("тревог", "опас", "риск", "фишинг", "красный флаг"), "high"),
    EmojiIntent("🛑", "stop", ("gifts", "liga"), ("стоп", "останов", "запрет", "не покупай", "не делай"), "high"),
    EmojiIntent("🔥", "heat", ("gifts", "liga"), ("горяч", "памп", "рывок", "жёст", "взорвал"), "high"),
    EmojiIntent("💥", "impact", ("gifts", "liga"), ("удар", "конфликт", "разнёс", "прорвал", "сломал"), "high"),
    EmojiIntent("🧨", "explosive", ("gifts", "liga"), ("взрыв", "жёст", "провал", "разнос", "скандал"), "high"),
    EmojiIntent("👀", "attention", ("gifts", "liga"), ("смотри", "заметь", "пропуска", "деталь", "увид")),
    EmojiIntent("🔍", "research", ("gifts", "liga"), ("провер", "исслед", "разбор", "поиск", "скаут")),
    EmojiIntent("🧠", "analysis", ("gifts", "liga"), ("анализ", "решен", "понима", "тактик", "контекст")),
    EmojiIntent("🎯", "precision", ("gifts", "liga"), ("точн", "цель", "удар", "выбор", "план")),
    EmojiIntent("💡", "idea", ("gifts", "liga"), ("идея", "инсайт", "придумал", "вывод", "принцип")),
    EmojiIntent("🧩", "system", ("gifts", "liga"), ("систем", "механик", "стратег", "схем", "собрать")),
    EmojiIntent("🤝", "trust", ("gifts", "liga"), ("довер", "команд", "партнёр", "сообществ", "переговор")),
    EmojiIntent("🏆", "win", ("gifts", "liga"), ("побед", "успех", "лидер", "лучший", "чемпион"), "high"),
    EmojiIntent("🚀", "growth", ("gifts", "liga"), ("рост", "запуск", "стартап", "карьер", "прорыв"), "high"),
    EmojiIntent("💎", "rarity", ("gifts",), ("редк", "модел", "атрибут", "коллекц")),
    EmojiIntent("📉", "market", ("gifts",), ("floor", "цена", "рынок", "ликвид", "спрос")),
    EmojiIntent("📈", "rise", ("gifts",), ("рост", "прибыл", "выручк", "продаж", "масштаб")),
    EmojiIntent("💰", "money", ("gifts",), ("деньг", "доход", "бизнес", "монетиз", "бюджет")),
    EmojiIntent("💸", "loss", ("gifts",), ("потер", "убыт", "потрат", "дорог", "провал"), "high"),
    EmojiIntent("🎁", "gift", ("gifts",), ("подарок", "gift", "telegram", "stars", "аукцион")),
    EmojiIntent("📲", "digital", ("gifts",), ("telegram", "mini app", "бот", "приложен", "платформ")),
    EmojiIntent("🤖", "ai", ("gifts",), ("нейро", "искусственн", " ai ", "алгоритм", "автомат")),
    EmojiIntent("🎨", "design", ("gifts",), ("дизайн", "цвет", "стил", "автор", "упаков")),
    EmojiIntent("🔒", "security", ("gifts",), ("безопас", "приват", "парол", "аккаунт", "защит")),
    EmojiIntent("⚽", "football", ("liga",), ("мяч", "матч", "футбол", "поле", "игрок")),
    EmojiIntent("⚡", "speed", ("liga",), ("скорост", "рывок", "реакц", "быстр", "темп"), "high"),
    EmojiIntent("👟", "technique", ("liga",), ("техник", "касан", "дриблинг", "пас", "стопа")),
    EmojiIntent("🧱", "defence", ("liga",), ("защит", "блок", "отбор", "защитник", "линия")),
    EmojiIntent("🧤", "goalkeeper", ("liga",), ("вратар", "голкипер", "сейв", "ворот", "перчат")),
    EmojiIntent("🏃", "movement", ("liga",), ("бег", "движен", "рывок", "вынослив", "позиц")),
    EmojiIntent("🏋", "training", ("liga",), ("трениров", "упражн", "нагруз", "сил", "зал")),
    EmojiIntent("💤", "recovery", ("liga",), ("сон", "восстанов", "отдых", "устал", "режим")),
    EmojiIntent("🎥", "video", ("liga",), ("видео", "нарезк", "камер", "хайлайт", "аналитик")),
    EmojiIntent("🗣", "communication", ("liga",), ("тренер", "раздевал", "разговор", "партнёр", "капитан")),
)

# These are fallback priorities, not a compulsory signature. The renderer picks
# two relevant signs that actually exist in the selected custom-emoji family.
BRAND_ANCHORS = {
    "liga": ("⚽", "⚡", "🎯", "👟", "🏃", "🏆", "🧱", "🎥", "🧠", "👀"),
    "gifts": ("💡", "🧠", "🎯", "💰", "📈", "🎨", "📲", "💎", "🔍", "👀"),
}
NEUTRAL_ANCHORS = {
    "gifts": ("💡", "🧠", "🎯", "🔍", "🧩", "🤝", "🚀", "💎", "📲", "🎨"),
    "liga": ("⚽", "🎯", "👀", "🧠", "👟", "🏃", "🎥", "🤝", "🏆", "🚀"),
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
    cap=max(0,min(int(limit),3))
    seed=hashlib.sha256(f"{channel}|{value}".encode("utf-8")).digest()
    ranked: list[tuple[float, int, str]] = []
    for index, item in enumerate(CATALOG):
        fallback = item.fallback.replace("\ufe0f", "")
        if channel not in item.channels or fallback not in normalized:
            continue
        matches=sum(term.strip() in value for term in item.terms)
        if not matches: continue
        energy=3 if item.energy=="high" else 1
        tie=int.from_bytes(hashlib.sha256(seed+fallback.encode("utf-8")).digest()[:2],"big")
        ranked.append((matches*100+energy,tie,fallback))
    ranked.sort(reverse=True)
    chosen=[]
    for _,_,fallback in ranked:
        if fallback not in chosen and len(chosen)<cap: chosen.append(fallback)

    # If the text has fewer explicit matches, rotate through all suitable signs
    # from the installed family. This is deterministic for one post but avoids a
    # permanent default pair across the feed.
    neutral=[fallback for fallback in NEUTRAL_ANCHORS.get(channel,()) if fallback in normalized]
    if neutral:
        offset=int.from_bytes(seed[:4],"big")%len(neutral)
        neutral=neutral[offset:]+neutral[:offset]
    for fallback in neutral:
        if fallback not in chosen and len(chosen)<cap: chosen.append(fallback)

    pool=[]
    for item in CATALOG:
        fallback=item.fallback.replace("\ufe0f","")
        if channel in item.channels and fallback in normalized and fallback not in chosen and fallback not in pool: pool.append(fallback)
    if pool:
        offset=int.from_bytes(seed[:4],"big")%len(pool)
        pool=pool[offset:]+pool[:offset]
    for fallback in pool:
        if fallback not in chosen and len(chosen)<cap: chosen.append(fallback)
    return tuple(chosen)


def semantic_custom_emojis(text: str, channel: str, available: dict[str, str], limit: int = 3) -> dict[str, str]:
    """Return only topic-aware glyphs that occur in the rendered post."""
    cap = max(0, min(limit, 3))
    normalized = {str(key).replace("\ufe0f", ""): str(item) for key, item in available.items()}
    chosen=[]
    for fallback in normalized:
        if fallback in text and fallback not in chosen and len(chosen) < cap:
            chosen.append(fallback)
    return {fallback: normalized[fallback] for fallback in chosen if str(normalized[fallback]).isdigit()}


def missing_brand_anchors(channel: str, available: dict[str, str]) -> tuple[str, ...]:
    count=len(semantic_anchors("",channel,available,2))
    return tuple("◇" for _ in range(max(0,2-count)))
