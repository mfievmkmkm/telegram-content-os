from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Сегодня", callback_data="v2:today"), InlineKeyboardButton(text="＋ Создать", callback_data="panel:generate")],
        [InlineKeyboardButton(text="◫ Проекты", callback_data="v2:projects"), InlineKeyboardButton(text="◷ Календарь", callback_data="panel:scheduled")],
        [InlineKeyboardButton(text="▶ Студия", callback_data="v2:studio"), InlineKeyboardButton(text="↗ Рост", callback_data="panel:analytics")],
        [InlineKeyboardButton(text="▣ Продажи", callback_data="panel:orders"), InlineKeyboardButton(text="◇ Знания", callback_data="panel:courses")],
        [InlineKeyboardButton(text="⚙ Система", callback_data="panel:system")],
    ])


def studio_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пост", callback_data="panel:generate"), InlineKeyboardButton(text="Shorts", callback_data="v2:shorts")],
        [InlineKeyboardButton(text="Карточки", callback_data="v2:cards"), InlineKeyboardButton(text="Мемы", callback_data="v2:memes")],
        [InlineKeyboardButton(text="Remix", callback_data="v2:remix")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="panel:home")],
    ])


def projects_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Gifts Intelligence", callback_data="v2:project:gifts")],
        [InlineKeyboardButton(text="⚽ Liga Progress", callback_data="v2:project:liga")],
        [InlineKeyboardButton(text="⚡ AI Content Lab", callback_data="v2:project:lab")],
        [InlineKeyboardButton(text="‹ Назад", callback_data="panel:home")],
    ])


def shorts_review_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✓ В монтаж", callback_data=f"shortsv2:approve:{draft_id}")],
        [InlineKeyboardButton(text="🔥 Жёстче", callback_data=f"shortsv2:tone:punchy:{draft_id}"), InlineKeyboardButton(text="😂 Мемнее", callback_data=f"shortsv2:tone:meme:{draft_id}")],
        [InlineKeyboardButton(text="✂ Короче", callback_data=f"shortsv2:shorter:{draft_id}"), InlineKeyboardButton(text="↻ Другой хук", callback_data=f"shortsv2:hook:{draft_id}")],
        [InlineKeyboardButton(text="🎙 Голос", callback_data=f"shortsv2:voices:{draft_id}"), InlineKeyboardButton(text="◫ Кадры", callback_data=f"shortsv2:scenes:{draft_id}")],
        [InlineKeyboardButton(text="‹ К посту", callback_data=f"back:{draft_id}")],
    ])


def voice_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Lera · энергия", callback_data=f"shortsv2:voice:yandex_lera:{draft_id}"), InlineKeyboardButton(text="Marina · уверенно", callback_data=f"shortsv2:voice:yandex_marina:{draft_id}")],
        [InlineKeyboardButton(text="Anton · спортивно", callback_data=f"shortsv2:voice:yandex_anton:{draft_id}"), InlineKeyboardButton(text="ElevenLabs", callback_data=f"shortsv2:voice:elevenlabs:{draft_id}")],
        [InlineKeyboardButton(text="🎙 Свой MP3", callback_data=f"shortsv2:voice:upload:{draft_id}")],
        [InlineKeyboardButton(text="‹ Назад", callback_data=f"shortsv2:review:{draft_id}")],
    ])
