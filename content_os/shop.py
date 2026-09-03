from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


@dataclass(frozen=True)
class Offer:
    key: str
    title: str
    price: str
    description: str


OFFERS = {
    "liga_episode": Offer("liga_episode", "Разбор игрового эпизода", "от 490 ₽", "Разберём решение игрока, позицию и следующий ход без пустой мотивации"),
    "liga_plan": Offer("liga_plan", "Персональный план на 7 дней", "790 ₽", "План тренировок под позицию, слабое место и доступный инвентарь"),
    "liga_passport": Offer("liga_passport", "Player Passport", "от 1 490 ₽", "Карточка футболиста и накопительный отчёт по присланным матчам"),
    "gifts_audit": Offer("gifts_audit", "Вскрытие одного Gift", "490 ₽", "Редкость, ликвидность, спрос и ловушки без обещаний прибыли"),
    "gifts_portfolio": Offer("gifts_portfolio", "Разбор коллекции", "990 ₽", "Что в портфеле живое, что зависло и где риск скрыт красивой обёрткой"),
    "content_pack": Offer("content_pack", "Контент-система для Telegram", "от 4 900 ₽", "Настроим темы, стиль, автопостинг и редактор под канал клиента"),
}


def storefront() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Для футболиста", callback_data="shop:category:liga")],
        [InlineKeyboardButton(text="🎁 Для владельца Gifts", callback_data="shop:category:gifts")],
        [InlineKeyboardButton(text="🧠 Для Telegram-канала", callback_data="shop:offer:content_pack")],
    ])


def category_keyboard(category: str) -> InlineKeyboardMarkup:
    keys = ["liga_episode", "liga_plan", "liga_passport"] if category == "liga" else ["gifts_audit", "gifts_portfolio"]
    rows = [[InlineKeyboardButton(text=f"{OFFERS[key].title} · {OFFERS[key].price}", callback_data=f"shop:offer:{key}")] for key in keys]
    rows.append([InlineKeyboardButton(text="‹ Назад", callback_data="shop:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def offer_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оставить заявку", callback_data=f"shop:order:{key}")],
        [InlineKeyboardButton(text="‹ К витрине", callback_data="shop:home")],
    ])
