from __future__ import annotations

import hashlib
from datetime import date

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .football_challenges import Challenge, LIBRARY, daily_challenge


def _text(challenge: Challenge) -> str:
    return (
        f"⚽ <b>{challenge.title}</b>\n\n"
        f"{challenge.task}\n\n"
        f"<b>Зачёт:</b> {challenge.success_metric}\n"
        f"<b>Пруф:</b> {challenge.proof}\n\n"
        "Не пытайся сделать красиво. Сделай чисто — и только потом ускоряйся"
    )


def _keyboard(challenge: Challenge) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✚ В черновик Liga", callback_data=f"v2:challenge:draft:{challenge.key}")],
        [InlineKeyboardButton(text="🔄 Другой челлендж", callback_data=f"v2:challenge:next:{challenge.key}")],
        [InlineKeyboardButton(text="🏠 Home", callback_data="panel:home")],
    ])


def _select(key: str | None = None) -> Challenge:
    if key:
        found = next((item for item in LIBRARY if item.key == key), None)
        if found:
            return found
    return daily_challenge("community", "all", date.today())


def _next(current_key: str) -> Challenge:
    current = _select(current_key)
    candidates = [item for item in LIBRARY if item.key != current.key]
    if not candidates:
        return current
    seed = hashlib.sha256(f"next:{current.key}:{date.today().isoformat()}".encode()).hexdigest()
    return candidates[int(seed[:8], 16) % len(candidates)]


def install(legacy):
    router = Router(name="football-challenges-v2")

    @router.callback_query(F.data == "v2:challenge")
    async def show(c: CallbackQuery):
        if not legacy.admin(c):
            return
        challenge = _select()
        await c.answer()
        await c.message.answer(_text(challenge), parse_mode=ParseMode.HTML, reply_markup=_keyboard(challenge))

    @router.callback_query(F.data.startswith("v2:challenge:next:"))
    async def reroll(c: CallbackQuery):
        if not legacy.admin(c):
            return
        current_key = c.data.rsplit(":", 1)[-1]
        challenge = _next(current_key)
        await c.answer("Другой челлендж")
        await c.message.edit_text(_text(challenge), parse_mode=ParseMode.HTML, reply_markup=_keyboard(challenge))

    @router.callback_query(F.data.startswith("v2:challenge:draft:"))
    async def to_draft(c: CallbackQuery):
        if not legacy.admin(c):
            return
        key = c.data.rsplit(":", 1)[-1]
        challenge = _select(key)
        plain = (
            f"⚽ {challenge.title}\n\n{challenge.task}\n\n"
            f"Зачёт: {challenge.success_metric}\nПруф: {challenge.proof}\n\n"
            "Не пытайся сделать красиво. Сделай чисто — и только потом ускоряйся"
        )
        source_hash = hashlib.sha256(f"challenge:{challenge.key}:{date.today().isoformat()}".encode()).hexdigest()
        try:
            draft_id = legacy.db.save_draft("liga", "challenge", plain, 86, challenge.title, "", source_hash)
        except Exception as exc:
            return await c.answer(str(exc)[:160], show_alert=True)
        await c.answer("Черновик создан")
        await legacy.review(draft_id)

    legacy.dp.include_router(router)
    return router
