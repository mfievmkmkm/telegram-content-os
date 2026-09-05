from __future__ import annotations

import html
import json
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .remix import RemixService
from .formatting import decorate_post, plain_text
from .hooks import score_hook


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
        legacy.db.set(f"v2:remix:{raw}",json.dumps({
            "channel":draft["channel_key"],"long":bundle.telegram_long,"short":bundle.telegram_short,
            "meme":bundle.meme,"shorts":bundle.shorts_script,"poll_question":bundle.poll_question,
            "poll_options":list(bundle.poll_options),"sales":bundle.sales_bridge},ensure_ascii=False))
        await c.message.answer("<b>Что отправить дальше в фабрику?</b>",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▤ Большой пост",callback_data=f"remixv2:save:{raw}:long"),InlineKeyboardButton(text="▥ Короткий пост",callback_data=f"remixv2:save:{raw}:short")],
            [InlineKeyboardButton(text="◉ Мем",callback_data=f"remixv2:save:{raw}:meme"),InlineKeyboardButton(text="🎬 Shorts",callback_data=f"remixv2:save:{raw}:shorts")],
            [InlineKeyboardButton(text="◎ Опрос",callback_data=f"remixv2:save:{raw}:poll")],
            [InlineKeyboardButton(text="‹ К исходнику",callback_data=f"back:{raw}")],
        ]))

    @router.callback_query(F.data.startswith("remixv2:save:"))
    async def remix_save(c:CallbackQuery):
        if not legacy.admin(c): return
        parts=c.data.split(":")
        if len(parts)!=4 or not parts[2].isdigit(): return await c.answer("Remix устарел",show_alert=True)
        source_id,kind=int(parts[2]),parts[3]
        try: data=json.loads(legacy.db.get(f"v2:remix:{source_id}") or "{}")
        except (TypeError,ValueError,json.JSONDecodeError): data={}
        channel=str(data.get("channel") or "")
        if channel not in {"gifts","liga"}: return await c.answer("Remix не найден",show_alert=True)
        if kind=="poll":
            options="\n".join(f"{i}. {x}" for i,x in enumerate(data.get("poll_options") or [],1)); raw_text=f"{data.get('poll_question','')}\n\n{options}"
        else: raw_text=str(data.get(kind) or "")
        if len(raw_text.strip())<8: return await c.answer("Этот формат пуст",show_alert=True)
        text=decorate_post(raw_text,channel); score=score_hook(plain_text(text))[0]
        draft_id=legacy.db.save_draft(channel,f"remix_{kind}",text,score,f"Remix #{source_id}","",None)
        await c.answer("Передано Creative Director"); await legacy.review(draft_id)

    legacy.keyboard = remix_keyboard
    legacy.dp.include_router(router)
    return service, router
