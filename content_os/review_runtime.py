from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from .creative_director import render_report
from .director_service import ContentDirectorService
from .editorial_memory import EditorialMemory
from .visual_renderer import preview_variants, render_card


log = logging.getLogger("content-os.review-v2")


def install_review(legacy):
    memory = EditorialMemory(legacy.db)
    director = ContentDirectorService(legacy.editor, legacy.db, memory)
    router = Router(name="content-review-v2")

    base_keyboard = legacy.keyboard
    base_gift_card = legacy.gift_card
    base_liga_card = legacy.liga_card
    base_use_gift = legacy.use_gift_card
    base_use_liga = legacy.use_liga_card

    def review_keyboard(draft_id):
        markup = base_keyboard(draft_id)
        rows = [list(row) for row in markup.inline_keyboard]
        rows.insert(-1, [InlineKeyboardButton(text="🎨 Другие карточки", callback_data=f"visualv2:options:{draft_id}")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def use_gift_card(draft_id):
        return memory.selected_variant(draft_id) is not None or base_use_gift(draft_id)

    def use_liga_card(draft_id):
        return memory.selected_variant(draft_id) is not None or base_use_liga(draft_id)

    def gift_card(text, format_key="intelligence"):
        return render_card("gifts", text, format_key, memory.variant_for_text(text))

    def liga_card(text, format_key="football"):
        return render_card("liga", text, format_key, memory.variant_for_text(text))

    async def review_v2(draft_id):
        chat = legacy.db.get("admin_chat_id")
        if not chat:
            return
        try:
            result = await director.polish(draft_id)
        except Exception as exc:
            log.exception("Creative Director failed")
            return await legacy.bot.send_message(
                int(chat),
                f"❌ <b>Creative Director не завершил проверку</b>\n\n{html.escape(str(exc)[:350])}",
                parse_mode=ParseMode.HTML,
            )
        draft = result.draft
        report = result.decision.report
        if not result.decision.approved:
            details = html.escape(render_report(report))
            return await legacy.bot.send_message(
                int(chat),
                f"🛑 <b>Материал остановлен до редактора</b>\n\n<pre>{details}</pre>\n\nАвтоправок: {result.rewrites}",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🔄 Другой заход", callback_data=f"rewrite:{draft_id}"),
                        InlineKeyboardButton(text="🔥 Жёстче", callback_data=f"harder:{draft_id}"),
                    ],
                    [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{draft_id}")],
                ]),
            )

        director.remember(result)
        channel = draft["channel_key"]
        wants_card = base_use_gift(draft_id) if channel == "gifts" else base_use_liga(draft_id)
        selected = memory.selected_variant(draft_id)
        if wants_card and selected is None:
            recent = memory.recent_visuals(channel)
            used = {int(value.rsplit(":", 1)[-1]) for value in recent[-2:] if value.startswith("variant:") and value.rsplit(":", 1)[-1].isdigit()}
            selected = next((variant for variant in range(3) if variant not in used), 0)
            memory.select_variant(draft_id, selected, draft["text"])
            memory.remember_visual(channel, f"variant:{selected}")

        if wants_card:
            try:
                image = render_card(channel, draft["text"], draft["format_key"], selected or 0)
                await legacy.bot.send_photo(
                    int(chat),
                    BufferedInputFile(image, filename=f"{channel}-{draft_id}-v{selected or 0}.png"),
                    caption=f"🎨 Visual Director · вариант {chr(65 + (selected or 0))}",
                )
            except Exception:
                log.exception("Visual preview failed for draft %s", draft_id)
        elif channel != "gifts":
            image = await legacy.discover_image(draft["source_url"] or "")
            if image:
                try:
                    await legacy.bot.send_photo(int(chat), image, caption="Иллюстрация из материала")
                except Exception:
                    log.info("Source image unavailable during v2 review: %s", image)

        quality = f"CD {report.score}/100"
        if result.rewrites:
            quality += f" · исправлено ×{result.rewrites}"
        cfg = legacy.CHANNELS[channel]
        await legacy.bot.send_message(
            int(chat),
            f"{cfg['emoji']} <b>{cfg['title']} · {draft['format_key']} · хук {draft['hook_score']}/5 · {quality}</b>\n\n{legacy.render(channel, draft['text'])}",
            parse_mode=ParseMode.HTML,
            reply_markup=review_keyboard(draft_id),
            disable_web_page_preview=True,
        )

    @router.callback_query(F.data.startswith("visualv2:options:"))
    async def visual_options(c: CallbackQuery):
        if not legacy.admin(c): return
        raw = c.data.rsplit(":", 1)[-1]
        if not raw.isdigit(): return await c.answer("Некорректный пост", show_alert=True)
        draft = legacy.db.draft(int(raw))
        if not draft: return await c.answer("Черновик не найден", show_alert=True)
        await c.answer("Готовлю три варианта…")
        try:
            images = preview_variants(draft["channel_key"], draft["text"], draft["format_key"], 3)
            media = [
                InputMediaPhoto(media=BufferedInputFile(image, filename=f"preview-{raw}-{index}.png"), caption=f"Вариант {chr(65 + index)}")
                for index, image in enumerate(images)
            ]
            await c.message.answer_media_group(media)
        except Exception as exc:
            log.exception("Visual alternatives failed")
            return await c.message.answer(f"❌ Карточки не собраны: {html.escape(str(exc)[:300])}", parse_mode=ParseMode.HTML)
        selected = memory.selected_variant(raw)
        rows = [[
            InlineKeyboardButton(text=("✓ " if selected == index else "") + chr(65 + index), callback_data=f"visualv2:choose:{raw}:{index}")
            for index in range(3)
        ], [InlineKeyboardButton(text="↩️ К посту", callback_data=f"back:{raw}")]]
        await c.message.answer("🎨 <b>Какой визуал оставляем?</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    @router.callback_query(F.data.startswith("visualv2:choose:"))
    async def choose_visual(c: CallbackQuery):
        if not legacy.admin(c): return
        parts = c.data.split(":")
        if len(parts) != 4 or not parts[2].isdigit() or not parts[3].isdigit():
            return await c.answer("Некорректный вариант", show_alert=True)
        draft_id, variant = int(parts[2]), int(parts[3])
        draft = legacy.db.draft(draft_id)
        if not draft: return await c.answer("Черновик не найден", show_alert=True)
        memory.select_variant(draft_id, variant, draft["text"])
        memory.remember_visual(draft["channel_key"], f"variant:{variant}")
        await c.answer(f"Вариант {chr(65 + variant)} выбран", show_alert=True)
        try:
            image = render_card(draft["channel_key"], draft["text"], draft["format_key"], variant)
            await c.message.answer_photo(
                BufferedInputFile(image, filename=f"selected-{draft_id}-{variant}.png"),
                caption=f"✅ Выбран вариант {chr(65 + variant)}",
                reply_markup=review_keyboard(draft_id),
            )
        except Exception:
            log.exception("Selected visual preview failed")

    # Publish/review use module globals at call time, so these replacements affect
    # legacy workflows without copying the large monolithic handler file.
    legacy.keyboard = review_keyboard
    legacy.gift_card = gift_card
    legacy.liga_card = liga_card
    legacy.use_gift_card = use_gift_card
    legacy.use_liga_card = use_liga_card
    legacy.review = review_v2
    legacy.dp.include_router(router)
    return director, memory, router
