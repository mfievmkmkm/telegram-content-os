import html

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, Message

from .sales import DiagnosticInput, recommend
from .shop import OFFERS, category_keyboard, offer_keyboard, shop_nav, storefront


class ClientState(StatesGroup):
    waiting_brief=State()
    waiting_diagnostic=State()


def create_shop_runtime(settings,db,editor,admin_bot):
    """Customer-facing sales runtime: outcome first, catalog second."""
    shop_bot=Bot(settings.shop_bot_token); router=Router(); dp=Dispatcher(); dp.include_router(router)

    def track(user_id,event_type,source="",offer_key=""):
        try: db.save_funnel_event(user_id,event_type,source,offer_key)
        except Exception: pass

    def home_keyboard(): return storefront(settings.gifts_subscription_bot_username)

    HOME=("<b>CONTENT OS LAB</b>\n\n"
          "Не выбирай технологию. Выбери, что должно измениться.\n\n"
          "⚽ Улучшить игру\n"
          "🎬 Получить контент\n"
          "📲 Прокачать Telegram\n"
          "🤖 Убрать ручную работу\n"
          "🎁 Gifts Intelligence\n\n"
          "<i>Если не уверен — диагностика подберёт следующий шаг без продажи вслепую</i>")

    def diagnostic_keyboard():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚽ Улучшить игру",callback_data="sales:goal:football")],
            [InlineKeyboardButton(text="🎬 Делать Shorts / Reels",callback_data="sales:goal:shorts")],
            [InlineKeyboardButton(text="📲 Прокачать Telegram",callback_data="sales:goal:telegram")],
            [InlineKeyboardButton(text="🤖 Автоматизировать работу",callback_data="sales:goal:automation")],
            [InlineKeyboardButton(text="🎁 Gifts Intelligence",callback_data="sales:goal:gifts")],
            [InlineKeyboardButton(text="✍️ Своя задача",callback_data="sales:goal:custom")],
            [InlineKeyboardButton(text="🏠 Главная",callback_data="shop:home")],
        ])

    def recommendation_markup(rec):
        pkg=rec.package
        if pkg.key=="gifts_intelligence":
            username=settings.gifts_subscription_bot_username or "vsdvscbot"
            return InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Открыть Gifts Intelligence →",url=f"https://t.me/{username}?start=shop")],
                [InlineKeyboardButton(text="↩️ Другая задача",callback_data="shop:diagnostic"),InlineKeyboardButton(text="🏠 Главная",callback_data="shop:home")],
            ])
        legacy_key=next((key for key in pkg.legacy_offer_keys if key in OFFERS),None)
        if legacy_key:
            return InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Посмотреть решение →",callback_data=f"shop:offer:{legacy_key}")],
                [InlineKeyboardButton(text="↩️ Другая задача",callback_data="shop:diagnostic"),InlineKeyboardButton(text="🏠 Главная",callback_data="shop:home")],
            ])
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Другая задача",callback_data="shop:diagnostic"),InlineKeyboardButton(text="🏠 Главная",callback_data="shop:home")],
        ])

    async def show_recommendation(message,rec,source="direct"):
        pkg=rec.package
        track(message.chat.id,"recommendation",source,pkg.key)
        missing=("\n\n<b>Чтобы начать, ещё нужно:</b> "+", ".join(html.escape(x) for x in rec.missing)) if rec.missing else ""
        deliverables="\n".join(f"• {html.escape(item)}" for item in pkg.deliverables)
        text=(f"<b>Под твою задачу: {html.escape(pkg.title)}</b>\n\n"
              f"{html.escape(pkg.promise)}\n\n"
              f"<b>Что получишь</b>\n{deliverables}\n\n"
              f"<b>Стоимость:</b> {html.escape(pkg.price_label)}\n"
              f"<b>Срок:</b> {html.escape(pkg.turnaround)}\n\n"
              f"<i>{html.escape(rec.reason)} · уверенность {rec.confidence}%</i>{missing}")
        await message.answer(text,parse_mode=ParseMode.HTML,reply_markup=recommendation_markup(rec))

    @router.message(CommandStart())
    @router.message(Command("shop"))
    async def home(message:Message,state:FSMContext):
        await state.clear(); payload=(message.text or "").partition(" ")[2].strip()
        source="liga_post" if payload=="service_liga" else "gifts_post" if payload=="service_gifts" else payload or "direct"
        await state.update_data(shop_source=source); track(message.from_user.id,"landing",source)
        if payload=="service_gifts":
            rec=recommend(DiagnosticInput(goal="Gifts Intelligence",vertical="gifts"))
            return await show_recommendation(message,rec,source)
        if payload=="service_liga":
            rec=recommend(DiagnosticInput(goal="Хочу улучшить свою игру",vertical="football"))
            return await show_recommendation(message,rec,source)
        await message.answer(HOME,parse_mode=ParseMode.HTML,reply_markup=home_keyboard())

    @router.callback_query(F.data=="shop:home")
    async def back(c:CallbackQuery,state:FSMContext):
        await state.clear(); await c.message.edit_text(HOME,parse_mode=ParseMode.HTML,reply_markup=home_keyboard()); await c.answer()

    @router.callback_query(F.data.startswith("shop:category:"))
    async def category(c:CallbackQuery,state:FSMContext):
        current=await state.get_data(); source=current.get("shop_source","direct")
        await state.clear(); await state.update_data(shop_source=source)
        key=c.data.rsplit(":",1)[-1]
        if key not in {"liga","services"}: return await c.answer("Раздел не найден",show_alert=True)
        if key=="liga":
            text="<b>FOOTBALL LAB</b>\n\n>От конкретного эпизода к плану развития. Выбери формат, если уже точно знаешь, что тебе нужно"
        else:
            text="<b>AI CONTENT LAB</b>\n\nКонтент и автоматизация как готовый результат. Каталог — для тех, кто уже определился"
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
        await c.message.edit_text(f"<b>Заявка · {html.escape(OFFERS[key].title)}</b>\n\n{prompt}\n\nК файлу обязательно добавь короткую подпись с задачей",parse_mode=ParseMode.HTML,reply_markup=shop_nav(f"shop:offer:{key}")); await c.answer()

    @router.message(ClientState.waiting_brief)
    async def brief(message:Message,state:FSMContext):
        value=(message.text or message.caption or "").strip()
        if len(value)<5: return await message.answer("Добавь к файлу подпись или опиши задачу хотя бы одним предложением")
        data=await state.get_data(); key=data.get("offer_key",""); item=OFFERS.get(key)
        if not item: await state.clear(); return await message.answer("Открой /start и выбери услугу заново")
        username=message.from_user.username or ""
        try: order_id=db.save_service_order(message.from_user.id,username,key,value)
        except Exception: order_id=f"TG-{message.message_id}"
        admin_chat=db.get("admin_chat_id")
        if admin_chat:
            contact=f"@{username}" if username else f"ID <code>{message.from_user.id}</code>"
            await admin_bot.send_message(int(admin_chat),f"<b>Новая заявка #{order_id}</b>\n\n{html.escape(item.title)} · {html.escape(item.price)}\nКлиент: {contact}\nИсточник: {html.escape(str(data.get('shop_source','direct')))}\n\n{html.escape(value)}",parse_mode=ParseMode.HTML)
            if message.document or message.video or message.photo or message.audio or message.voice:
                try: await shop_bot.forward_message(int(admin_chat),message.chat.id,message.message_id)
                except Exception: await admin_bot.send_message(int(admin_chat),"⚠️ В заявке есть вложение. Если оно не показалось здесь, открой диалог с клиентом по контакту выше")
        track(message.from_user.id,"order_created",data.get("shop_source","direct"),key); await state.clear()
        await message.answer(f"<b>Заявка #{order_id} принята</b>\n\nСначала проверим материал и зафиксируем результат. После этого подтвердим объём и цену",parse_mode=ParseMode.HTML,reply_markup=home_keyboard())

    @router.callback_query(F.data=="shop:diagnostic")
    async def diagnostic(c:CallbackQuery,state:FSMContext):
        await state.clear()
        await c.message.edit_text("<b>Что должно измениться?</b>\n\nСначала результат. Инструмент подберём потом",parse_mode=ParseMode.HTML,reply_markup=diagnostic_keyboard()); await c.answer()

    @router.callback_query(F.data.startswith("sales:goal:"))
    async def diagnostic_goal(c:CallbackQuery,state:FSMContext):
        goal=c.data.rsplit(":",1)[-1]
        labels={
            "football":"Футбол — хочу улучшить свою игру",
            "shorts":"Нужны Shorts / Reels",
            "telegram":"Хочу прокачать Telegram-канал и продажи",
            "automation":"Хочу автоматизировать Telegram и контент-процесс",
            "gifts":"Хочу Gifts Intelligence",
        }
        data=await state.get_data(); source=data.get("shop_source","direct")
        if goal=="custom":
            await state.set_state(ClientState.waiting_diagnostic)
            await state.update_data(shop_source=source)
            await c.message.edit_text("<b>Опиши результат одним сообщением</b>\n\nНе «нужен AI», а что должно стать лучше: больше заявок, ролики, автоматизация, игра, Telegram и т.д.",parse_mode=ParseMode.HTML,reply_markup=shop_nav("shop:diagnostic")); return await c.answer()
        rec=recommend(DiagnosticInput(goal=labels.get(goal,goal),vertical="football" if goal=="football" else "gifts" if goal=="gifts" else ""))
        await c.answer()
        await show_recommendation(c.message,rec,source)

    @router.message(ClientState.waiting_diagnostic)
    async def diagnose(message:Message,state:FSMContext):
        brief=(message.text or "").strip()
        if len(brief)<12: return await message.answer("Нужно чуть конкретнее: что должно измениться после нашей работы?")
        data=await state.get_data(); source=data.get("shop_source","direct")
        rec=recommend(DiagnosticInput(goal=brief,notes=brief))
        await state.clear(); await show_recommendation(message,rec,source)

    async def setup_commands():
        await shop_bot.set_my_commands([
            BotCommand(command="start",description="подобрать решение"),
            BotCommand(command="shop",description="витрина решений"),
        ])
        await shop_bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    dp.startup.register(setup_commands)
    return shop_bot,dp
