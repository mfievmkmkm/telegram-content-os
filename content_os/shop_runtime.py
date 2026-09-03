import html
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .channels import CHANNELS
from .formatting import telegram_html
from .shop import OFFERS, category_keyboard, offer_keyboard, storefront


class ClientState(StatesGroup):
    waiting_brief=State()
    waiting_diagnostic=State()


def create_shop_runtime(settings,db,editor,admin_bot):
    """A customer-only bot sharing the same catalog and database with the editor."""
    shop_bot=Bot(settings.shop_bot_token); router=Router(); dp=Dispatcher(); dp.include_router(router)

    def track(user_id,event_type,source="",offer_key=""):
        try: db.save_funnel_event(user_id,event_type,source,offer_key)
        except Exception: pass

    @router.message(CommandStart())
    @router.message(Command("shop"))
    async def home(message:Message,state:FSMContext):
        await state.clear(); payload=(message.text or "").partition(" ")[2].strip()
        source="liga_post" if payload=="service_liga" else "gifts_post" if payload=="service_gifts" else "direct"
        await state.update_data(shop_source=source); track(message.from_user.id,"landing",source)
        await message.answer("<b>Выбери задачу, которую нужно закрыть</b>",parse_mode=ParseMode.HTML,reply_markup=storefront())

    @router.callback_query(F.data=="shop:home")
    async def back(c:CallbackQuery,state:FSMContext):
        await state.clear(); await c.message.edit_text("<b>Выбери задачу</b>",parse_mode=ParseMode.HTML,reply_markup=storefront()); await c.answer()

    @router.callback_query(F.data.startswith("shop:category:"))
    async def category(c:CallbackQuery):
        key=c.data.rsplit(":",1)[-1]
        if key not in {"liga","gifts"}: return await c.answer("Раздел не найден",show_alert=True)
        title="Футбольная лаборатория" if key=="liga" else "Gifts Intelligence"
        await c.message.edit_text(f"<b>{title}</b>\n\nВыбери конкретную задачу",parse_mode=ParseMode.HTML,reply_markup=category_keyboard(key)); await c.answer()

    @router.callback_query(F.data.startswith("shop:offer:"))
    async def offer(c:CallbackQuery,state:FSMContext):
        key=c.data.rsplit(":",1)[-1]; item=OFFERS.get(key)
        if not item: return await c.answer("Услуга не найдена",show_alert=True)
        data=await state.get_data(); track(c.from_user.id,"offer_view",data.get("shop_source","direct"),key)
        await c.message.edit_text(f"<b>{html.escape(item.title)}</b>\n{html.escape(item.price)}\n\n{html.escape(item.description)}",parse_mode=ParseMode.HTML,reply_markup=offer_keyboard(key)); await c.answer()

    @router.callback_query(F.data.startswith("shop:order:"))
    async def order(c:CallbackQuery,state:FSMContext):
        key=c.data.rsplit(":",1)[-1]
        if key not in OFFERS: return await c.answer("Услуга не найдена",show_alert=True)
        current=await state.get_data(); await state.set_state(ClientState.waiting_brief)
        await state.update_data(offer_key=key,shop_source=current.get("shop_source","direct"))
        await c.message.edit_text("<b>Одним сообщением:</b> что у тебя сейчас и какой результат нужен?",parse_mode=ParseMode.HTML); await c.answer()

    @router.message(ClientState.waiting_brief)
    async def brief(message:Message,state:FSMContext):
        value=(message.text or message.caption or "").strip()
        if len(value)<5: return await message.answer("Опиши задачу чуть подробнее")
        data=await state.get_data(); key=data.get("offer_key",""); item=OFFERS.get(key)
        if not item: await state.clear(); return await message.answer("Открой /start и выбери услугу заново")
        username=message.from_user.username or ""
        try: order_id=db.save_service_order(message.from_user.id,username,key,value)
        except Exception: order_id=f"TG-{message.message_id}"
        admin_chat=db.get("admin_chat_id")
        if admin_chat:
            contact=f"@{username}" if username else f"ID <code>{message.from_user.id}</code>"
            await admin_bot.send_message(int(admin_chat),f"<b>Новая заявка #{order_id}</b>\n\n{html.escape(item.title)} · {html.escape(item.price)}\nКлиент: {contact}\n\n{html.escape(value)}",parse_mode=ParseMode.HTML)
        track(message.from_user.id,"order_created",data.get("shop_source","direct"),key); await state.clear()
        await message.answer(f"<b>Заявка #{order_id} принята</b>\n\nМы посмотрим задачу и напишем без оплаты вслепую",parse_mode=ParseMode.HTML,reply_markup=storefront())

    @router.callback_query(F.data=="shop:diagnostic")
    async def diagnostic(c:CallbackQuery,state:FSMContext):
        await state.set_state(ClientState.waiting_diagnostic)
        await c.message.edit_text("Начни сообщение со слова <b>Футбол</b> или <b>Gifts</b>, затем опиши проблему",parse_mode=ParseMode.HTML); await c.answer()

    @router.message(ClientState.waiting_diagnostic)
    async def diagnose(message:Message,state:FSMContext):
        brief=(message.text or "").strip(); lower=brief.lower()
        if len(brief)<20 or not (lower.startswith("футбол") or lower.startswith("gifts")):
            return await message.answer("Начни с «Футбол» или «Gifts» и добавь подробности")
        channel="liga" if lower.startswith("футбол") else "gifts"; offer_key="liga_episode" if channel=="liga" else "gifts_audit"
        system=CHANNELS[channel]["voice"]+"\nДай три коротких честных наблюдения и следующий шаг. Не придумывай факты. До 650 знаков"
        try: result=await editor.llm(system,brief,.65)
        except Exception: result="Для честного вывода нужен один конкретный эпизод или Gift, принятое решение и результат"
        await state.clear(); await message.answer(telegram_html(result)+"\n\n<b>Разобрать на конкретных данных?</b>",parse_mode=ParseMode.HTML,reply_markup=offer_keyboard(offer_key))

    return shop_bot,dp
