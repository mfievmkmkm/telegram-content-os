from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .shorts import ShortsStudio, brief_text, review_keyboard, style_keyboard, voice_keyboard
from .shorts.ui import rendered_keyboard, subtitle_keyboard


log = logging.getLogger("content-os.v2")


def draft_keyboard(draft_id: int | str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ В канал", callback_data=f"publish:{draft_id}"),
            InlineKeyboardButton(text="⏰ Выбрать время", callback_data=f"schedule:{draft_id}"),
        ],
        [
            InlineKeyboardButton(text="🔥 Жёстче", callback_data=f"harder:{draft_id}"),
            InlineKeyboardButton(text="🔄 Другой заход", callback_data=f"rewrite:{draft_id}"),
        ],
        [
            InlineKeyboardButton(text="✂️ Короче", callback_data=f"short:{draft_id}"),
            InlineKeyboardButton(text="🎬 Shorts Studio", callback_data=f"shortsv2:start:{draft_id}"),
        ],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{draft_id}")],
    ])


def main_keyboard() -> InlineKeyboardMarkup:
    """Product-first navigation: creation and growth first, technical controls last."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Создать", callback_data="panel:generate"),
            InlineKeyboardButton(text="📅 Календарь", callback_data="panel:scheduled"),
        ],
        [
            InlineKeyboardButton(text="🎬 Studio", callback_data="panel:shorts"),
            InlineKeyboardButton(text="📊 Growth", callback_data="panel:analytics"),
        ],
        [
            InlineKeyboardButton(text="⚽ Football", callback_data="panel:football"),
            InlineKeyboardButton(text="🎁 Gifts", callback_data="panel:gifts"),
        ],
        [
            InlineKeyboardButton(text="🛒 Sales", callback_data="panel:orders"),
            InlineKeyboardButton(text="🧠 Knowledge", callback_data="panel:courses"),
        ],
        [InlineKeyboardButton(text="⚙️ System", callback_data="panel:system")],
    ])


def install(legacy):
    """Install v2 features without editing the legacy monolith.

    The migration branch imports the stable runtime, swaps presentation functions,
    and registers isolated v2 callbacks. Main remains untouched until the milestone
    passes a real Railway smoke test.
    """
    router = Router(name="content-os-v2")
    studio = ShortsStudio(legacy.settings, legacy.editor, legacy.db)

    # Functions in legacy.__main__ resolve globals at call time, so the replacement
    # upgrades every existing review/menu entry point while preserving old handlers.
    legacy.keyboard = draft_keyboard
    legacy.main_keyboard = main_keyboard

    async def show_review(c: CallbackQuery, job_id: int | str, *, new_message: bool = False):
        brief = studio.sessions.load(job_id)
        if brief is None:
            return await c.answer("Shorts-сессия не найдена", show_alert=True)
        text = brief_text(brief)
        if not new_message and getattr(c.message, "text", None):
            try:
                await legacy.safe_edit_text(c.message, text, parse_mode=ParseMode.HTML, reply_markup=review_keyboard(job_id))
                return
            except Exception:
                pass
        await c.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=review_keyboard(job_id))

    async def render_job(c: CallbackQuery, job_id: int | str):
        if not studio.renderer.ready:
            return await c.message.answer(
                "✅ <b>Сценарий подтверждён</b>\n\nShorts Worker пока не подключён к этой версии. Монтаж не запускал — сценарий сохранён.",
                parse_mode=ParseMode.HTML,
            )
        status = await c.message.answer(
            "🎬 <b>Собираю Shorts · 0%</b>\n\nСейчас: подготовка",
            parse_mode=ParseMode.HTML,
        )

        async def progress(value: int):
            phase = "озвучка" if value < 20 else "кадры" if value < 75 else "субтитры и финальный рендер"
            try:
                await status.edit_text(
                    f"🎬 <b>Собираю Shorts · {value}%</b>\n\nСейчас: {phase}",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

        try:
            _, video, provider, warning = await studio.render(job_id, progress)
        except Exception as exc:
            log.exception("Shorts v2 render failed")
            return await status.edit_text(
                f"❌ <b>Shorts не собрался</b>\n\n{html.escape(str(exc)[:350])}",
                parse_mode=ParseMode.HTML,
            )
        brief = studio.sessions.load(job_id)
        await status.delete()
        provider_note = f" · {provider}" if provider else ""
        warning_note = f"\n⚠️ {warning}" if warning else ""
        await legacy.bot.send_video(
            c.message.chat.id,
            BufferedInputFile(video, filename=f"shorts-{job_id}.mp4"),
            caption=(f"🎬 {brief.caption if brief else 'Shorts готов'}{provider_note}{warning_note}")[:1024],
            supports_streaming=True,
            reply_markup=rendered_keyboard(job_id),
        )

    @router.callback_query(F.data.startswith("shortsv2:start:"))
    async def start_short(c: CallbackQuery):
        if not legacy.admin(c): return
        raw = c.data.rsplit(":", 1)[-1]
        if not raw.isdigit(): return await c.answer("Некорректный пост", show_alert=True)
        draft = legacy.db.draft(int(raw))
        if not draft: return await c.answer("Черновик не найден", show_alert=True)
        await c.answer("Готовлю только сценарий…")
        try:
            job_id, brief = await studio.start(draft)
        except Exception as exc:
            log.exception("Shorts v2 script generation failed")
            return await c.message.answer(f"❌ Сценарий не собрался: {html.escape(str(exc)[:300])}", parse_mode=ParseMode.HTML)
        await c.message.answer(brief_text(brief), parse_mode=ParseMode.HTML, reply_markup=review_keyboard(job_id))

    @router.callback_query(F.data.startswith("shortsv2:review:"))
    async def review_short(c: CallbackQuery):
        if not legacy.admin(c): return
        await c.answer()
        await show_review(c, c.data.rsplit(":", 1)[-1])

    @router.callback_query(F.data.startswith("shortsv2:rewrite:"))
    async def rewrite_short(c: CallbackQuery):
        if not legacy.admin(c): return
        parts = c.data.split(":")
        if len(parts) != 4: return await c.answer("Некорректное действие", show_alert=True)
        _, _, mode, job_id = parts
        await c.answer("Переписываю только сценарий…")
        try:
            await studio.rewrite(job_id, mode)
        except Exception as exc:
            return await c.message.answer(f"❌ {html.escape(str(exc)[:300])}", parse_mode=ParseMode.HTML)
        await show_review(c, job_id, new_message=not bool(getattr(c.message, "text", None)))

    @router.callback_query(F.data.startswith("shortsv2:voices:"))
    async def voices(c: CallbackQuery):
        if not legacy.admin(c): return
        job_id = c.data.rsplit(":", 1)[-1]
        brief = studio.sessions.load(job_id)
        if not brief: return await c.answer("Shorts-сессия не найдена", show_alert=True)
        await c.answer()
        await c.message.answer(
            "🎙 <b>Голос</b>\n\nРусский SpeechKit — основной автоматический режим. ElevenLabs оставляем как premium-вариант.",
            parse_mode=ParseMode.HTML,
            reply_markup=voice_keyboard(job_id, brief.channel, brief.voice_preset),
        )

    @router.callback_query(F.data.startswith("shortsv2:voice:"))
    async def choose_voice(c: CallbackQuery):
        if not legacy.admin(c): return
        parts = c.data.split(":")
        if len(parts) != 4: return await c.answer("Некорректный голос", show_alert=True)
        _, _, preset, job_id = parts
        brief = studio.choose_voice(job_id, preset)
        await c.answer("Голос выбран")
        await c.message.answer(brief_text(brief), parse_mode=ParseMode.HTML, reply_markup=review_keyboard(job_id))

    @router.callback_query(F.data.startswith("shortsv2:styles:"))
    async def styles(c: CallbackQuery):
        if not legacy.admin(c): return
        job_id = c.data.rsplit(":", 1)[-1]
        brief = studio.sessions.load(job_id)
        if not brief: return await c.answer("Shorts-сессия не найдена", show_alert=True)
        await c.answer()
        await c.message.answer(
            "🎨 <b>Подача</b>\n\nСтиль меняет сам сценарий, поэтому после выбора текст будет пересобран до монтажа.",
            parse_mode=ParseMode.HTML,
            reply_markup=style_keyboard(job_id, brief.delivery_preset),
        )

    @router.callback_query(F.data.startswith("shortsv2:style:"))
    async def choose_style(c: CallbackQuery):
        if not legacy.admin(c): return
        parts = c.data.split(":")
        if len(parts) != 4: return await c.answer("Некорректный стиль", show_alert=True)
        _, _, preset, job_id = parts
        await c.answer("Пересобираю сценарий под стиль…")
        try:
            brief = await studio.restyle(job_id, preset)
        except Exception as exc:
            return await c.message.answer(f"❌ {html.escape(str(exc)[:300])}", parse_mode=ParseMode.HTML)
        await c.message.answer(brief_text(brief), parse_mode=ParseMode.HTML, reply_markup=review_keyboard(job_id))

    @router.callback_query(F.data.startswith("shortsv2:subtitles:"))
    async def subtitles(c: CallbackQuery):
        if not legacy.admin(c): return
        job_id = c.data.rsplit(":", 1)[-1]
        brief = studio.sessions.load(job_id)
        if not brief: return await c.answer("Shorts-сессия не найдена", show_alert=True)
        await c.answer()
        await c.message.answer(
            "💬 <b>Субтитры</b>\n\nPunch — самый динамичный. Clean — спокойнее. Sport и Meme дают более выраженный характер.",
            parse_mode=ParseMode.HTML,
            reply_markup=subtitle_keyboard(job_id, brief.subtitle_preset),
        )

    @router.callback_query(F.data.startswith("shortsv2:subtitle:"))
    async def choose_subtitle(c: CallbackQuery):
        if not legacy.admin(c): return
        parts = c.data.split(":")
        if len(parts) != 4: return await c.answer("Некорректный стиль", show_alert=True)
        _, _, preset, job_id = parts
        brief = studio.choose_subtitle(job_id, preset)
        await c.answer("Субтитры выбраны")
        if brief.approved:
            return await render_job(c, job_id)
        await c.message.answer(brief_text(brief), parse_mode=ParseMode.HTML, reply_markup=review_keyboard(job_id))

    @router.callback_query(F.data.startswith("shortsv2:scenes:"))
    async def remix_scenes(c: CallbackQuery):
        if not legacy.admin(c): return
        job_id = c.data.rsplit(":", 1)[-1]
        current = studio.sessions.load(job_id)
        if not current: return await c.answer("Shorts-сессия не найдена", show_alert=True)
        was_approved = current.approved
        await c.answer("Подбираю другие кадры…")
        try:
            await studio.remix_scenes(job_id)
        except Exception as exc:
            return await c.message.answer(f"❌ {html.escape(str(exc)[:300])}", parse_mode=ParseMode.HTML)
        if was_approved:
            return await render_job(c, job_id)
        await show_review(c, job_id, new_message=not bool(getattr(c.message, "text", None)))

    @router.callback_query(F.data.startswith("shortsv2:approve:"))
    async def approve_short(c: CallbackQuery):
        if not legacy.admin(c): return
        job_id = c.data.rsplit(":", 1)[-1]
        try:
            studio.approve(job_id)
        except Exception as exc:
            return await c.answer(str(exc)[:150], show_alert=True)
        await c.answer("Сценарий принят")
        await render_job(c, job_id)

    @router.callback_query(F.data.startswith("shortsv2:back:"))
    async def back_to_post(c: CallbackQuery):
        if not legacy.admin(c): return
        job_id = c.data.rsplit(":", 1)[-1]
        brief = studio.sessions.load(job_id)
        if not brief or brief.draft_id is None:
            return await c.answer("Исходный пост не найден", show_alert=True)
        await c.answer()
        await c.message.answer(
            f"↩️ <b>Пост #{brief.draft_id}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=draft_keyboard(brief.draft_id),
        )

    legacy.dp.include_router(router)
    return studio, router
