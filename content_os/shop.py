from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


@dataclass(frozen=True)
class Offer:
    key: str
    category: str
    title: str
    price: str
    description: str
    result: str
    turnaround: str


OFFERS = {
    "liga_episode": Offer("liga_episode","liga","Разбор одного эпизода","390 ₽","Ты присылаешь момент и указываешь себя. Разбираем позицию, решение до приёма и лучший следующий ход","Размеченный эпизод + 3 конкретные правки","до 24 часов"),
    "liga_match": Offer("liga_match","liga","Разбор матча игрока","1 490 ₽","Разбираем матч или нарезку без пустых оценок: решения, открывания, игра без мяча и повторяющиеся ошибки","Видеоразбор + отчёт + план исправления","1–3 дня"),
    "liga_plan": Offer("liga_plan","liga","Персональный план на 14 дней","990 ₽","Программа под позицию, слабое место, график и доступный инвентарь","План тренировок, контрольные точки и тест прогресса","до 24 часов"),
    "liga_passport": Offer("liga_passport","liga","Player Passport","1 990 ₽","Игровой профиль футболиста, который обновляется после новых матчей","Сильные стороны, риски, метрики и карта развития","2–3 дня"),
    "ai_short": Offer("ai_short","services","Shorts / Reels под ключ","990 ₽","Хук, сценарий, озвучка, монтаж и субтитры для ролика до 60 секунд","Готовый вертикальный MP4","1–2 дня"),
    "ai_visuals": Offer("ai_visuals","services","AI-креативы для товара","590 ₽","Четыре цепляющих изображения под объявление, пост или карточку услуги","4 готовых изображения в одном стиле","до 24 часов"),
    "ai_music": Offer("ai_music","services","Трек или джингл под задачу","790 ₽","Идея, текст и генерация трека под ролик, подарок или бренд","2 версии + короткий фрагмент","1–2 дня"),
    "tg_pack": Offer("tg_pack","services","Упаковка Telegram-канала","2 990 ₽","Позиционирование, оформление, рубрики и стартовый контент без нейросетевой стерильности","Стиль канала + 10 тем + 5 готовых постов","2–4 дня"),
    "content_system": Offer("content_system","services","Контент-бот для Telegram","от 6 990 ₽","Редактор, генерация постов, расписание и публикация под конкретный канал","Рабочий бот и инструкция запуска","от 5 дней"),
}


def storefront(gifts_bot_username: str="vsdvscbot") -> InlineKeyboardMarkup:
    username=gifts_bot_username.strip().lstrip("@") or "vsdvscbot"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ LIGA PROGRESS · футбол",callback_data="shop:category:liga")],
        [InlineKeyboardButton(text="⚡ DIGITAL LAB · услуги",callback_data="shop:category:services")],
        [InlineKeyboardButton(text="🎁 GIFTS INTELLIGENCE · подписка",url=f"https://t.me/{username}?start=shop")],
        [InlineKeyboardButton(text="🎯 Подобрать услугу бесплатно",callback_data="shop:diagnostic")],
    ])


def category_keyboard(category: str) -> InlineKeyboardMarkup:
    keys=[key for key,item in OFFERS.items() if item.category==category]
    rows=[[InlineKeyboardButton(text=f"{OFFERS[key].title} · {OFFERS[key].price}",callback_data=f"shop:offer:{key}")] for key in keys]
    rows.append([InlineKeyboardButton(text="‹ На главную",callback_data="shop:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def offer_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оставить заявку →",callback_data=f"shop:order:{key}")],
        [InlineKeyboardButton(text="‹ К разделу",callback_data=f"shop:category:{OFFERS[key].category}")],
    ])
