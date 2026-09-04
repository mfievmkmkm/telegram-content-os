import html
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, Message

from .channels import CHANNELS
from .formatting import telegram_html
from .shop import OFFERS, category_keyboard, offer_keyboard, shop_nav, storefront


class ClientState(StatesGroup):
    waiting_brief=State()
    waiting_diagnostic=State()


def create_shop_runtime(settings,db,editor,admin_bot):
    """A customer-only bot sharing the same catalog and database with the editor."""
    shop_bot=Bot(settings.shop_bot_token); router=Router(); dp=Dispatcher(); dp.include_router(router)

    def track(user_id,event_type,source="",offer_key=""):
        try: db.save_funnel_event(user_id,event_type,source,offer_key)
        except Exception: pass

    def home_keyboard(): return storefront(settings.gifts_subscription_bot_username)

    HOME=("<b>НЕ ИЩИ УСЛУГУ. ВЫБЕРИ РЕЗУЛЬТАТ</b>\n\n"
          "⚽ Разбор игры и развитие футболиста\n"
          "⚡ Контент, видео, креативы и Telegram-боты\n"
          "🎁 Доступ к аналитике Telegram Gifts\n\n"
          "<i>Без оплаты вслепую — сначала уточним задачу</i>")

    @router.message(CommandStart())
    @router.message(Command("shop"))
    async def home(message:Message,state:FSMContext):
        await state.clear(); payload=(message.text or "").partition(" ")[2].strip()
        source="liga_post" if payload=="service_liga" else "gifts_post" if payload=="service_gifts" else "direct"
        await state.update_data(shop_source=source); track(message.from_user.id,"landing",source)
        await message.answer(HOME,parse_mode=ParseMode.HTML,reply_markup=home_keyboard())

    @router.callback_query(F.data=="shop:home")
    async def back(c:CallbackQuery,state:FSMContext):
        await state.clear(); await c.message.edit_text(HOME,parse_mode=ParseMode.HTML,reply_markup=home_keyboard()); await c.answer()

    @router.callback_query(F.data.startswith("shop:category:"))
    async def category(c:CallbackQuery,state:FSMContext):
        await state.clear()
        key=c.data.rsplit(":",1)[-1]
        if key not in {"liga","services"}: return await c.answer("Раздел не найден",show_alert=True)
        if key=="liga":
            text="<b>LIGA PROGRESS · ИГРОВАЯ ЛАБОРАТОРИЯ</b>\n\nНе оцениваем талант по настроению. Находим конкретное решение, которое можно улучшить"
        else:
            text="<b>DIGITAL LAB · УСЛУГИ</b>\n\nНе продаём «нейросеть». Собираем готовый результат под твою задачу"
        await c.message.edit_text(text,parse_mode=ParseMode.HTML,reply_markup=category_keyboard(key)); await c.answer()

    @router.callback_query(F.data.startswith("shop:offer:"))
    async def offer(c:CallbackQuery,state:FSMContext):
        key=c.data.rsplit(":",1)[-1]; item=OFFERS.get(key)
        if not item: return await c.answer("Услуга не найдена",show_alert=True)
        data=await state.get_data(); source=data.get("shop_source","direct"); await state.clear(); await state.update_data(shop_source=source)
        track(c.from_user.id,"offer_view",source,key)
        text=(f"<b>{html.escape(item.title)}</b>\n"
              f"<b>{html.escape(item.price)}</b>\n\n"
              f"{html.escape(item.description)}\n\n"
              f"<b>Получишь:</b> {html.escape(item.result)}\n"
              f"<b>Срок:</b> {html.escape(item.turnaround)}")
        await c.message.edit_text(text,parse_mode=ParseMode.HTML,reply_markup=offer_keyboard(key)); await c.answer()

    @router.callback_query(F.data.startswith("shop:order:"))
    async def order(c:CallbackQuery,state:FSMContext):
        key=c.data.rsplit(":",1)[-1]
        if key not in OFFERS: return await c.answer("Услуга не найдена",show_alert=True)
        current=await state.get_data(); await state.set_state(ClientState.waiting_brief)
        await state.update_data(offer_key=key,shop_source=current.get("shop_source","direct"))
        prompt="Пришли видео или ссылку и напиши позицию игрока" if OFFERS[key].category=="liga" else "Опиши задачу, площадку и какой результат хочешь получить"
        await c.message.edit_text(f"<b>Заявка · {html.escape(OFFERS[key].title)}</b>\n\n{prompt}\n\nМожно отправить текст, ссылку или файл одним сообщением",parse_mode=ParseMode.HTML,reply_markup=shop_nav(f"shop:offer:{key}")); await c.answer()

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
        await message.answer(f"<b>Заявка #{order_id} принята</b>\n\nСначала посмотрим материал и уточним результат. Только потом подтвердим цену",parse_mode=ParseMode.HTML,reply_markup=home_keyboard())

    @router.callback_query(F.data=="shop:diagnostic")
    async def diagnostic(c:CallbackQuery,state:FSMContext):
        await state.set_state(ClientState.waiting_diagnostic)
        await c.message.edit_text("Одним сообщением напиши направление и задачу\n\nНапример:\n<code>Футбол — теряюсь при выходе из прессинга</code>\n<code>Контент — нужны ролики для товара</code>\n<code>Gifts — хочу понять, что даёт подписка</code>",parse_mode=ParseMode.HTML,reply_markup=shop_nav()); await c.answer()

    @router.message(ClientState.waiting_diagnostic)
    async def diagnose(message:Message,state:FSMContext):
        brief=(message.text or "").strip(); lower=brief.lower()
        if len(brief)<20 or not any(lower.startswith(x) for x in ("футбол","контент","услуги","gifts","гифт")):
            return await message.answer("Начни с «Футбол», «Контент» или «Gifts» и добавь подробности")
        channel="liga" if lower.startswith("футбол") else "gifts"; offer_key="liga_episode" if channel=="liga" else "ai_short"
        system=CHANNELS[channel]["voice"]+"\nДай три коротких честных наблюдения и следующий шаг. Не придумывай факты. До 650 знаков"
        try: result=await editor.llm(system,brief,.65)
        except Exception: result="Для честного вывода нужен один конкретный эпизод или Gift, принятое решение и результат"
        await state.clear()
        if lower.startswith(("gifts","гифт")):
            username=settings.gifts_subscription_bot_username or "vsdvscbot"
            keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть Gifts Intelligence →",url=f"https://t.me/{username}?start=shop")],[InlineKeyboardButton(text="‹ Назад",callback_data="shop:home"),InlineKeyboardButton(text="🏠 Главная",callback_data="shop:home")]])
        else: keyboard=offer_keyboard(offer_key)
        await message.answer(telegram_html(result)+"\n\n<b>Следующий шаг</b>",parse_mode=ParseMode.HTML,reply_markup=keyboard)

    async def setup_commands():
        await shop_bot.set_my_commands([
            BotCommand(command="start",description="главная витрина"),
            BotCommand(command="shop",description="каталог услуг"),
        ])
        await shop_bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    dp.startup.register(setup_commands)
    return shop_bot,dp
