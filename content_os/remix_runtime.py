from __future__ import annotations

import asyncio
import html
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .remix import RemixService
from .remix_store import RemixStore, save_poll
from .formatting import decorate_post, plain_text
from .hooks import score_hook
from .fact_layer import FactStore
from .shorts import brief_text, review_keyboard

log = logging.getLogger("content-os.remix-v2")
KINDS = {"long": "telegram_long", "short": "telegram_short", "meme": "meme", "shorts": "shorts_script", "sales": "sales_bridge", "poll": "poll_question"}
LABELS = {"telegram_long": "Большой пост", "telegram_short": "Короткий пост", "meme": "Мем", "shorts_script": "Shorts", "sales_bridge": "Продажный мост", "poll_question": "Вопрос опроса", "poll_options": "Варианты опроса"}


def bundle_keyboard(bundle_id, source_id):
    def button(label, kind):
        return InlineKeyboardButton(text=label, callback_data=f"remixv2:save:{bundle_id}:{kind}")
    return InlineKeyboardMarkup(inline_keyboard=[
        [button("▤ Большой пост", "long"), button("▥ Короткий пост", "short")],
        [button("◉ Мем", "meme"), button("🎬 Shorts", "shorts")],
        [button("◎ Опрос", "poll"), button("↗ Продажный мост", "sales")],
        [button("Большой + мост", "saleslong"), button("Короткий + мост", "salesshort")],
        [InlineKeyboardButton(text="‹ К исходнику", callback_data=f"back:{source_id}"),
         InlineKeyboardButton(text="⌂ Главная", callback_data="v2:home")],
    ])


async def send_block(message, title, text):
    # Split before escaping. Count UTF-16 units too, so supplementary emoji are safe.
    chunk = ""
    size = 0
    for char in text:
        width = len(html.escape(char).encode("utf-16-le")) // 2
        if size + width > 3000:
            await message.answer(f"<b>{html.escape(title)}</b>\n\n{html.escape(chunk)}", parse_mode=ParseMode.HTML)
            chunk, size = "", 0
        chunk += char
        size += width
    if chunk:
        await message.answer(f"<b>{html.escape(title)}</b>\n\n{html.escape(chunk)}", parse_mode=ParseMode.HTML)


def install_remix(legacy, studio=None):
    service = RemixService(legacy.editor)
    store = RemixStore(legacy.db)
    router = Router(name="content-remix-v2")
    base_keyboard = legacy.keyboard
    save_lock = asyncio.Lock()
    generating = set()

    def remix_keyboard(draft_id):
        markup = base_keyboard(draft_id)
        rows = [list(row) for row in markup.inline_keyboard]
        rows.insert(-1, [InlineKeyboardButton(text="♻️ Remix", callback_data=f"remixv2:start:{draft_id}")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def show_bundle(c, bundle_id):
        value = store.load(bundle_id)
        if not value:
            return await c.message.answer("Набор не найден. Создай Remix заново.")
        data = value["formats"]
        keyboard = bundle_keyboard(bundle_id, value["source_id"])
        # Send the recovery controls before previews; the saved bundle survives send failures.
        await c.message.answer("<b>CONTENT REMIX</b>\nВыбери формат для проверки перед публикацией.", parse_mode=ParseMode.HTML, reply_markup=keyboard)
        if data.get("recovered_fields"):
            labels = ", ".join(LABELS.get(key, key) for key in data["recovered_fields"])
            await c.message.answer("Модель вернула неполный набор. Запасной вариант: " + labels + ". Проверь текст перед использованием.")
        for key in ("telegram_long", "telegram_short", "meme", "shorts_script", "sales_bridge"):
            await send_block(c.message, LABELS[key], data[key])
        await send_block(c.message, "Опрос", data["poll_question"] + "\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(data["poll_options"], 1)))

    @router.callback_query(F.data.startswith("remixv2:open:"))
    async def remix_open(c: CallbackQuery):
        if not legacy.admin(c): return
        await c.answer()
        await show_bundle(c, c.data.rsplit(":", 1)[-1])

    @router.callback_query(F.data.startswith("remixv2:start:"))
    async def remix_start(c: CallbackQuery):
        if not legacy.admin(c): return
        raw = c.data.rsplit(":", 1)[-1]
        if not raw.isdigit(): return await c.answer("Некорректный черновик", show_alert=True)
        draft = legacy.db.draft(int(raw))
        if not draft or dict(draft).get("status") == "deleted":
            return await c.answer("Черновик не найден или удалён", show_alert=True)
        if raw in generating: return await c.answer("Этот Remix уже собирается", show_alert=True)
        generating.add(raw)
        bundle_id = None
        try:
            await c.answer("Собираю набор форматов…")
            bundle = await service.create(draft["channel_key"], draft["text"])
            bundle_id = store.create(draft, bundle)
            await show_bundle(c, bundle_id)
        except Exception as exc:
            log.exception("Content Remix failed for draft %s", raw)
            callback = f"remixv2:open:{bundle_id}" if bundle_id else f"remixv2:start:{raw}"
            label = "Открыть сохранённый набор" if bundle_id else "Повторить Remix"
            await c.message.answer(
                f"❌ <b>{'Предпросмотр прерван, набор сохранён' if bundle_id else 'Remix не собран'}</b>\n\n{html.escape(str(exc)[:350])}",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=callback)], [InlineKeyboardButton(text="‹ К исходнику", callback_data=f"back:{raw}")]]),
            )
        finally:
            generating.discard(raw)

    @router.callback_query(F.data.startswith("remixv2:save:"))
    async def remix_save(c: CallbackQuery):
        if not legacy.admin(c): return
        parts = c.data.split(":")
        if len(parts) != 4: return await c.answer("Некорректная кнопка", show_alert=True)
        _, _, bundle_id, kind = parts
        if kind not in {*KINDS, "saleslong", "salesshort"}:
            return await c.answer("Неизвестный формат", show_alert=True)
        value = store.load(bundle_id)
        if not value:
            return await c.answer("Старый набор. Открой исходник и создай Remix заново", show_alert=True)
        source = legacy.db.draft(value["source_id"])
        if not source or dict(source).get("status") == "deleted":
            return await c.answer("Исходник удалён", show_alert=True)
        await c.answer("Открываю формат…")
        try:
            async with save_lock:
                result_id = store.result(bundle_id, kind)
                data, channel = value["formats"], value["channel"]
                source_hash = f"remix:{bundle_id}:{kind}"
                if kind != "shorts" and not result_id:
                    existing = legacy.db.draft_by_source_hash(channel, source_hash)
                    if existing:
                        result_id = existing["id"]
                        store.remember(bundle_id, kind, result_id)
                if kind == "shorts":
                    if studio is None: raise RuntimeError("Shorts Studio не подключён к этому runtime")
                    if result_id:
                        brief = studio.sessions.load(result_id)
                        if brief is None: raise ValueError("Shorts-сессия потеряна; создай новый Remix")
                    else:
                        result_id, brief = await studio.start_from_script(source, data["shorts_script"])
                        store.remember(bundle_id, kind, result_id)
                else:
                    if result_id:
                        draft = legacy.db.draft(result_id)
                        if not draft or dict(draft).get("status") == "deleted":
                            raise ValueError("Этот черновик удалён; создай новый Remix")
                    else:
                        if kind == "poll":
                            text = data["poll_question"] + "\n\n" + "\n".join(data["poll_options"])
                        elif kind in {"saleslong", "salesshort"}:
                            text = data["telegram_long" if kind == "saleslong" else "telegram_short"] + "\n\n" + data["sales_bridge"]
                        else:
                            text = data[KINDS[kind]]
                        text = decorate_post(text, channel)
                        try:
                            result_id = legacy.db.save_draft(channel, f"remix_{kind}", text, score_hook(plain_text(text))[0], f"Remix #{value['source_id']}", source["source_url"] or "", source_hash)
                        except Exception:
                            # A committed insert may have lost its response, or another
                            # process may have won the existing unique source-hash index.
                            existing = legacy.db.draft_by_source_hash(channel, source_hash)
                            if not existing: raise
                            result_id = existing["id"]
                        # Remember immediately: retries resume this draft, never create another.
                        store.remember(bundle_id, kind, result_id)
                    if kind == "poll":
                        save_poll(legacy.db, result_id, data["poll_question"], data["poll_options"])
                    facts = FactStore(legacy.db)
                    pack = facts.load(value["source_id"])
                    if pack: facts.save(result_id, pack)
            if kind == "shorts":
                await c.message.answer(brief_text(brief), parse_mode=ParseMode.HTML, reply_markup=review_keyboard(result_id))
            else:
                await legacy.review(result_id)
        except Exception as exc:
            log.exception("Remix handoff failed: %s/%s", bundle_id, kind)
            await c.message.answer(f"❌ Формат не открыт: {html.escape(str(exc)[:350])}\nНажми кнопку ещё раз после устранения причины.", parse_mode=ParseMode.HTML, reply_markup=bundle_keyboard(bundle_id, value["source_id"]))

    legacy.keyboard = remix_keyboard
    legacy.dp.include_router(router)
    return service, router
