from __future__ import annotations

import html
import os
from collections import Counter
from datetime import datetime

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .growth.attribution import normalize_event_type
from .release_gate import evaluate_release


def operator_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ TODAY", callback_data="v2:today"), InlineKeyboardButton(text="✚ CREATE", callback_data="panel:generate")],
        [InlineKeyboardButton(text="📁 PROJECTS", callback_data="v2:projects"), InlineKeyboardButton(text="📅 CALENDAR", callback_data="panel:scheduled")],
        [InlineKeyboardButton(text="🎬 STUDIO", callback_data="panel:shorts"), InlineKeyboardButton(text="📊 GROWTH", callback_data="v2:growth")],
        [InlineKeyboardButton(text="🛒 SALES", callback_data="panel:orders"), InlineKeyboardButton(text="🧠 KNOWLEDGE", callback_data="panel:courses")],
        [InlineKeyboardButton(text="⚙️ SYSTEM", callback_data="v2:readiness")],
    ])


def _nav() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✚ Создать", callback_data="panel:generate"), InlineKeyboardButton(text="📅 Календарь", callback_data="panel:scheduled")],
        [InlineKeyboardButton(text="🎬 Studio", callback_data="panel:shorts"), InlineKeyboardButton(text="📊 Growth", callback_data="v2:growth")],
        [InlineKeyboardButton(text="🏠 Home", callback_data="panel:home")],
    ])


def _safe_count(call, default=0):
    try:
        return len(call())
    except Exception:
        return default


def install(legacy):
    router = Router(name="content-os-operator-v2")
    legacy.main_keyboard = operator_keyboard

    @router.callback_query(F.data == "v2:today")
    async def today(c: CallbackQuery):
        if not legacy.admin(c):
            return
        now = datetime.now(legacy.settings.timezone)
        scheduled = _safe_count(lambda: legacy.db.future_scheduled(now.isoformat(), 50))
        orders = _safe_count(lambda: legacy.db.service_orders("new", 50))
        analytics_rows = _safe_count(lambda: legacy.db.analytics_summary(50))
        shorts = "online-config" if legacy.settings.mpt_base_url and legacy.settings.mpt_api_key else "not connected"
        matchlens = "online-config" if legacy.settings.matchlens_base_url and legacy.settings.matchlens_api_key else "experimental/off"
        text = (
            "<b>⚡ TODAY · CONTENT OS</b>\n\n"
            f"<b>Очередь</b>\nЗапланировано: {scheduled}\nНовых заказов: {orders}\nПостов с метриками: {analytics_rows}\n\n"
            f"<b>Production</b>\nShorts: {html.escape(shorts)}\nMatchLens: {html.escape(matchlens)}\n"
            f"Autopublish: {'ON ⚠️' if legacy.settings.auto_publish else 'OFF'}\n\n"
            "<i>Приоритет: сначала материалы и продажи, потом системные настройки</i>"
        )
        await c.answer()
        await c.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=_nav())

    @router.callback_query(F.data == "v2:projects")
    async def projects(c: CallbackQuery):
        if not legacy.admin(c):
            return
        text = (
            "<b>📁 PROJECTS</b>\n\n"
            "⚽ <b>LigaProgress</b>\nКонтент · Shorts · challenges · football products\n\n"
            "🎁 <b>Gifts Intelligence</b>\nКонтент · рынок · Shorts · переход в subscription bot\n\n"
            "🧪 <b>Content OS Lab</b>\nSales · услуги · автоматизация · эксперименты"
        )
        await c.answer()
        await c.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=_nav())

    @router.callback_query(F.data == "v2:growth")
    async def growth(c: CallbackQuery):
        if not legacy.admin(c):
            return
        try:
            events = legacy.db.funnel_events(5000)
        except Exception:
            events = []
        counts = Counter()
        sources = Counter()
        for event in events:
            event_type = normalize_event_type(str(event.get("event_type") if hasattr(event, "get") else event["event_type"]))
            if event_type:
                counts[event_type] += 1
            try:
                source = str(event.get("source") or "") if hasattr(event, "get") else str(event["source"] or "")
            except Exception:
                source = ""
            if source:
                sources[source] += 1
        top = "\n".join(f"• {html.escape(src[:50])} · {count}" for src, count in sources.most_common(3)) or "— данных пока мало"
        text = (
            "<b>📊 GROWTH</b>\n\n"
            f"Visits: {counts['visit']}\nLeads: {counts['lead']}\nOrders: {counts['order']}\nSales: {counts['sale']}\n\n"
            f"<b>Активные источники</b>\n{top}\n\n"
            "<i>Это наблюдаемые события. Причинность показываем только через контролируемые эксперименты</i>"
        )
        await c.answer()
        await c.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=_nav())

    @router.callback_query(F.data == "v2:readiness")
    async def readiness(c: CallbackQuery):
        if not legacy.admin(c):
            return
        gate = evaluate_release(os.environ, require_shorts=True)
        blocking = "\n".join(f"• {html.escape(item)}" for item in gate.blocking) or "• блокеров по env нет"
        warnings = "\n".join(f"• {html.escape(item)}" for item in gate.warnings) or "• предупреждений нет"
        text = (
            f"<b>⚙️ SYSTEM · {'READY' if gate.ready else 'NOT READY'}</b>\n\n"
            f"<b>Blocking</b>\n{blocking}\n\n<b>Warnings</b>\n{warnings}\n\n"
            "<i>Значения секретов никогда не показываются — только названия отсутствующих переменных</i>"
        )
        await c.answer()
        await c.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=_nav())

    legacy.dp.include_router(router)
    return router
