from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .remix import RemixService


log = logging.getLogger("content-os.remix-v2")


def install_remix(legacy):
    service = RemixService(legacy.editor)
    router = Router(name="content-remix-v2")
    base_keyboard = legacy.keyboard

    def remix_keyboard(draft_id):
        markup = base_keyboard(draft_id)
        rows = [list(row) for row in markup.inline_keyboard]
        rows.insert(-1, [InlineKeyboardButton(text="♻️ Remix", callback_data=f"remixv2:start:{draft_id}")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    @router.callback_query(F.data.startswith("remixv2:start:"))
    async def remix_start(c: CallbackQuery):
        if not legacy.admin(c):
            return
        raw = c.data.rsplit(":", 1)[-1]
        if not raw.isdigit():
            return await c.answer("Некорректный черновик", show_alert=True)
        draft = legacy.db.draft(int(raw))
        if not draft:
            return await c.answer("Черновик не найден", show_alert=True)
        await c.answer("Собираю набор форматов…")
        try:
            bundle = await service.create(draft["channel_key"], draft["text"])
        except Exception as exc:
            log.exception("Content Remix failed for draft %s", raw)
            return await c.message.answer(
                f"❌ <b>Remix не собран</b>\n\n{html.escape(str(exc)[:350])}",
                parse_mode=ParseMode.HTML,
            )

        poll = "\n".join(f"{index}. {html.escape(option)}" for index, option in enumerate(bundle.poll_options, 1))
        text = (
            "♻️ <b>CONTENT REMIX</b>\n\n"
            "<b>Короткий пост</b>\n"
            f"{html.escape(bundle.telegram_short)}\n\n"
            "<b>Мем</b>\n"
            f"{html.escape(bundle.meme)}\n\n"
            "<b>Опрос</b>\n"
            f"{html.escape(bundle.poll_question)}\n{poll}\n\n"
            "<b>Shorts</b>\n"
            f"{html.escape(bundle.shorts_script)}\n\n"
            "<b>Продажный мост</b>\n"
            f"{html.escape(bundle.sales_bridge)}"
        )
        await c.message.answer(text[:3900], parse_mode=ParseMode.HTML)
        if len(bundle.telegram_long) > 8:
            await c.message.answer(
                "<b>Большой пост</b>\n\n" + html.escape(bundle.telegram_long)[:3800],
                parse_mode=ParseMode.HTML,
            )

    legacy.keyboard = remix_keyboard
    legacy.dp.include_router(router)
    return service, router
