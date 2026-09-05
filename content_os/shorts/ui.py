from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .models import ShortBrief
from .presets import DELIVERY_PRESETS, VOICE_PRESETS


STYLE_LABELS = {
    "punchy": "🔥 Дерзко",
    "calm": "🧠 Спокойно",
    "meme": "😂 Мемно",
    "sport": "⚽ Спортивно",
}

SUBTITLE_PRESETS = {
    "punch": "Punch",
    "clean": "Clean",
    "sport": "Sport",
    "meme": "Meme",
}


def brief_text(brief: ShortBrief) -> str:
    style = STYLE_LABELS.get(brief.delivery_preset, brief.delivery_preset)
    voice = VOICE_PRESETS.get(brief.voice_preset)
    voice_title = voice.title if voice else brief.voice_preset
    return (
        f"🎬 <b>SHORTS STUDIO</b>\n"
        f"<code>{html.escape(str(brief.channel).upper())}</code> · {style}\n\n"
        f"<b>HOOK</b>\n{html.escape(brief.hook)}\n\n"
        f"<b>VOICEOVER</b>\n{html.escape(brief.voiceover)}\n\n"
        f"<b>{brief.word_count} слов</b> · ≈{brief.duration:g} сек\n"
        f"Голос: {html.escape(voice_title)}\n"
        f"Субтитры: {html.escape(SUBTITLE_PRESETS.get(brief.subtitle_preset, brief.subtitle_preset))}\n\n"
        "Монтаж начнётся только после подтверждения сценария"
    )


def review_keyboard(job_id: int | str) -> InlineKeyboardMarkup:
    key = str(job_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ В монтаж", callback_data=f"shortsv2:approve:{key}")],
        [
            InlineKeyboardButton(text="🔥 Жёстче", callback_data=f"shortsv2:rewrite:harder:{key}"),
            InlineKeyboardButton(text="😂 Мемнее", callback_data=f"shortsv2:rewrite:meme:{key}"),
        ],
        [
            InlineKeyboardButton(text="✂️ Короче", callback_data=f"shortsv2:rewrite:short:{key}"),
            InlineKeyboardButton(text="⚡ Другой хук", callback_data=f"shortsv2:rewrite:hook:{key}"),
        ],
        [
            InlineKeyboardButton(text="🎙 Голос", callback_data=f"shortsv2:voices:{key}"),
            InlineKeyboardButton(text="🎨 Стиль", callback_data=f"shortsv2:styles:{key}"),
        ],
        [InlineKeyboardButton(text="‹ К посту", callback_data=f"back:{key}")],
    ])


def voice_keyboard(job_id: int | str, channel: str, current: str = "auto_ru") -> InlineKeyboardMarkup:
    rows = []
    for key, preset in VOICE_PRESETS.items():
        if channel not in preset.channels:
            continue
        mark = "✓ " if key == current else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{preset.title}", callback_data=f"shortsv2:voice:{key}:{job_id}")])
    rows.append([InlineKeyboardButton(text="‹ Сценарий", callback_data=f"shortsv2:review:{job_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def style_keyboard(job_id: int | str, current: str = "punchy") -> InlineKeyboardMarkup:
    rows = []
    for key, preset in DELIVERY_PRESETS.items():
        mark = "✓ " if key == current else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{preset.title}", callback_data=f"shortsv2:style:{key}:{job_id}")])
    rows.append([InlineKeyboardButton(text="‹ Сценарий", callback_data=f"shortsv2:review:{job_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
