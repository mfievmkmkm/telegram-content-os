import asyncio
import html
import io
import json
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .channels import CHANNELS, SERIES
from .articles import fetch_article
from .config import load_settings
from .database import Database
from .supabase_database import SupabaseDatabase
from .editor import Editor
from .history import HistoryImporter
from .gifts_data import GiftsDataDesk
from .analytics import AnalyticsCollector
from .video import VideoFactory
from .formatting import plain_text, telegram_html
from .course_files import extract_course_text, course_chunks
from .media import discover_image
from .matchlens import MatchLensClient, MatchRequest, aggregate_passport, confidence_legend
from .football import FootballRadar, fixtures_keyboard_rows
from .shop import OFFERS, category_keyboard, offer_keyboard, shop_nav, storefront
from .shop_runtime import create_shop_runtime
from .funnel import summarize_funnel
from .brand_cards import gift_card, liga_card, use_gift_card, use_liga_card
from .mtproto_publish import PremiumPublisher

settings=load_settings()
db=(SupabaseDatabase(settings.supabase_url,settings.supabase_key,settings.timezone)
    if settings.supabase_url and settings.supabase_key else Database(settings.database_path,settings.timezone))
editor=Editor(settings,db)
videos=VideoFactory(settings,db,editor)
history=HistoryImporter(db,settings)
gifts_data=GiftsDataDesk(settings)
analytics=AnalyticsCollector(settings,db)
matchlens=MatchLensClient(settings,db)
football=FootballRadar(settings)
premium_publisher=PremiumPublisher(settings)
bot=Bot(settings.bot_token); router=Router(); dp=Dispatcher(); dp.include_router(router)
shop_bot,shop_dp=create_shop_runtime(settings,db,editor,bot) if settings.shop_bot_token else (None,None)
logging.basicConfig(level=getattr(logging, __import__("os").getenv("LOG_LEVEL","INFO").upper()))
log=logging.getLogger("content-os")

class ScheduleState(StatesGroup):
    waiting_datetime = State()

class GenerateState(StatesGroup):
    waiting_topic = State()
    waiting_url = State()
    waiting_rubric = State()

class MatchState(StatesGroup):
    waiting_source = State()
    waiting_player = State()
    waiting_mode = State()

class ShopState(StatesGroup):
    waiting_brief = State()
    waiting_diagnostic = State()

class CourseFileState(StatesGroup):
    waiting_file = State()

def admin(obj): return bool(obj.from_user and obj.from_user.username and obj.from_user.username.lower() in settings.admins)

def track(user_id,event_type,source="",offer_key=""):
    try: db.save_funnel_event(user_id,event_type,source,offer_key)
    except Exception: log.info("Funnel schema is not deployed yet")

def render(channel_key,text):
    raw=db.get(f"premium_emojis:{channel_key}") or "{}"
    try: custom=json.loads(raw)
    except (TypeError,json.JSONDecodeError): custom={}
    return telegram_html(text,custom)

async def premium_health():
    if not premium_publisher.ready: return "Bot API: переменные Premium-публикации не заполнены"
    lines=[]
    for key in ("liga","gifts"):
        ok,detail=await premium_publisher.probe(settings.channels[key])
        lines.append(f"{'✅' if ok else '❌'} {key}: {detail}")
    return "\n".join(lines)

def shop_health():
    try:
        db.service_orders(limit=1); db.funnel_events(limit=1)
        return "готов · отдельный бот" if shop_bot else "готов · внутри редактора"
    except Exception as exc: return f"НЕ РАБОТАЕТ · Supabase: {type(exc).__name__}: {str(exc)[:120]}"

def keyboard(draft_id):
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="✅ В канал",callback_data=f"publish:{draft_id}"),InlineKeyboardButton(text="⏰ Выбрать время",callback_data=f"schedule:{draft_id}")],
      [InlineKeyboardButton(text="🔥 Жёстче",callback_data=f"harder:{draft_id}"),InlineKeyboardButton(text="🔄 Другой заход",callback_data=f"rewrite:{draft_id}")],
      [InlineKeyboardButton(text="✂️ Короче",callback_data=f"short:{draft_id}"),InlineKeyboardButton(text="🎬 Shorts",callback_data=f"shorts:{draft_id}")],
      [InlineKeyboardButton(text="🗑 Удалить",callback_data=f"delete:{draft_id}")]])

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="✍️ Создать пост",callback_data="panel:generate"),InlineKeyboardButton(text="⏰ Очередь",callback_data="panel:scheduled")],
      [InlineKeyboardButton(text="⚽ Футбол и матчи",callback_data="panel:football"),InlineKeyboardButton(text="🎁 Gifts Data",callback_data="panel:gifts")],
      [InlineKeyboardButton(text="📚 Курсы",callback_data="panel:courses"),InlineKeyboardButton(text="📊 Аналитика постов",callback_data="panel:analytics")],
      [InlineKeyboardButton(text="📥 Заявки",callback_data="panel:orders"),InlineKeyboardButton(text="⚙️ Управление",callback_data="panel:system")]])

def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")]])

def admin_nav(back_callback="panel:home"):
    return InlineKeyboardMarkup(inline_keyboard=[[
      InlineKeyboardButton(text="‹ Назад",callback_data=back_callback),
      InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")]])

def match_job_keyboard(local_id,tracker_ids=(),result_url="",passport_players=()):
    rows=[]; ids=[str(value) for value in tracker_ids if str(value).isdigit()][:24]
    for index in range(0,len(ids),4):
        rows.append([InlineKeyboardButton(text=f"Игрок #{tracker}",callback_data=f"matchpick:{local_id}:{tracker}") for tracker in ids[index:index+4]])
    if result_url: rows.append([InlineKeyboardButton(text="📊 Открыть отчёт",url=result_url)])
    for player in list(passport_players)[:8]:
        rows.append([InlineKeyboardButton(text=f"➕ В паспорт: {player['display_name']}",callback_data=f"matchlink:{local_id}:{player['id']}")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить статус",callback_data=f"matchrefresh:{local_id}"),InlineKeyboardButton(text="‹ Футбол",callback_data="panel:football")])
    rows.append([InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def review(draft_id):
    draft=db.draft(draft_id); cfg=CHANNELS[draft["channel_key"]]; chat=db.get("admin_chat_id")
    if chat:
        branded=(draft["channel_key"]=="gifts" and use_gift_card(draft_id)) or (draft["channel_key"]=="liga" and use_liga_card(draft_id))
        if branded:
            card=gift_card if draft["channel_key"]=="gifts" else liga_card
            image=BufferedInputFile(card(draft["text"],draft["format_key"]),filename=f"{draft['channel_key']}-{draft_id}.png")
        else: image=await discover_image(draft["source_url"] or "") if draft["channel_key"]!="gifts" else None
        if image:
            try: await bot.send_photo(int(chat),image,caption="Предпросмотр фирменной карточки" if branded else "Предпросмотр иллюстрации")
            except Exception: log.info("Source image unavailable: %s",image)
        await bot.send_message(int(chat),f"{cfg['emoji']} <b>{cfg['title']} · {draft['format_key']} · хук {draft['hook_score']}/5</b>\n\n{render(draft['channel_key'],draft['text'])}",
                               parse_mode=ParseMode.HTML,reply_markup=keyboard(draft_id),disable_web_page_preview=True)

async def generate(channel_key):
    try:
        draft_id=None
        if channel_key=="gifts":
            counter=int(db.get("gifts_generation_counter") or 0)+1; db.set("gifts_generation_counter",str(counter))
            if counter%2==0:
                snapshot=await gifts_data.snapshot(); facts=gifts_data.editorial_facts(snapshot)
                if facts: draft_id=await editor.create_gifts_data_post(facts)
        if draft_id is None: draft_id=await editor.create(channel_key)
        if settings.auto_publish: await publish(draft_id)
        else: await review(draft_id)
    except Exception: log.exception("Generation failed for %s",channel_key)

async def publish(draft_id):
    draft=db.draft(draft_id); channel=settings.channels[draft["channel_key"]]
    sales_markup=None
    sales_link=None
    if settings.shop_cta_every and int(draft_id)%settings.shop_cta_every==0:
        me=await (shop_bot or bot).get_me(); slug="service_liga" if draft["channel_key"]=="liga" else "service_gifts"
        label="Разобрать мой эпизод" if draft["channel_key"]=="liga" else "Проверить мой Gift"
        sales_url=f"https://t.me/{me.username}?start={slug}"
        if premium_publisher.ready:
            sales_link=f'\n\n<a href="{sales_url}"><b>{label} →</b></a>'
        else:
            sales_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label,url=sales_url)]])
    rendered=render(draft["channel_key"],draft["text"])+(sales_link or "")
    bot_rendered=telegram_html(draft["text"])+(sales_link or "")
    wants_card=(draft["channel_key"]=="gifts" and use_gift_card(draft_id)) or (draft["channel_key"]=="liga" and use_liga_card(draft_id))
    # Telegram photo captions are limited; keep a long editorial post intact and text-only.
    card=gift_card if draft["channel_key"]=="gifts" else liga_card
    image=card(draft["text"],draft["format_key"]) if wants_card and len(plain_text(draft["text"]))<=1000 else None
    premium_error=None
    if premium_publisher.ready:
        try:
            sent=await premium_publisher.send(channel,rendered,image)
            mode="premium"
        except Exception as exc:
            premium_error=f"{type(exc).__name__}: {str(exc)[:220]}"; log.exception("Premium publish failed; falling back to Bot API")
            sent=None
    else: sent=None
    if sent is None and image:
        card_file=BufferedInputFile(image,filename=f"{draft['channel_key']}-{draft_id}.png")
        sent=await bot.send_photo(channel,card_file,caption=bot_rendered,parse_mode=ParseMode.HTML,reply_markup=sales_markup); mode="bot"
    elif sent is None and wants_card and not image:
        sent=await bot.send_message(channel,bot_rendered,parse_mode=ParseMode.HTML,disable_web_page_preview=True,reply_markup=sales_markup); mode="bot"
    elif sent is None:
        image=await discover_image(draft["source_url"] or "") if draft["channel_key"]!="gifts" else None
        if image:
            try: await bot.send_photo(channel,image)
            except Exception: log.info("Source image unavailable during publish: %s",image)
        sent=await bot.send_message(channel,bot_rendered,parse_mode=ParseMode.HTML,disable_web_page_preview=True,reply_markup=sales_markup); mode="bot"
    message_id=getattr(sent,"message_id",None) or getattr(sent,"id",None)
    if not message_id: raise RuntimeError("Telegram отправил пост, но не вернул ID сообщения")
    db.update(draft_id,status="published",published_at=datetime.now(settings.timezone).isoformat(),published_message_id=message_id)
    return mode,premium_error

@router.message(CommandStart())
async def start(message:Message,state:FSMContext):
    if not admin(message):
        payload=(message.text or "").partition(" ")[2].strip()
        if shop_bot:
            me=await shop_bot.get_me(); target=f"https://t.me/{me.username}?start={payload or 'direct'}"
            return await message.answer("🛍 <b>Магазин работает в отдельном боте</b>\n\nТам Liga Progress, Digital Lab и подписка Gifts Intelligence",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть магазин →",url=target)]]))
        source="liga_post" if payload=="service_liga" else "gifts_post" if payload=="service_gifts" else "direct"
        await state.update_data(shop_source=source); track(message.from_user.id,"landing",source)
        if payload=="service_liga": return await message.answer("<b>Хочешь понять, что ты реально сделал в эпизоде?</b>\n\nВыбери формат разбора",parse_mode=ParseMode.HTML,reply_markup=category_keyboard("liga"))
        if payload=="service_gifts": return await message.answer("<b>Gifts Intelligence</b>\n\nАналитика и сигналы доступны в подписочном боте",parse_mode=ParseMode.HTML,reply_markup=storefront(settings.gifts_subscription_bot_username))
        return await message.answer("<b>Выбери результат</b>",parse_mode=ParseMode.HTML,reply_markup=storefront(settings.gifts_subscription_bot_username))
    db.set("admin_chat_id",str(message.chat.id)); await message.answer("🧠 <b>Content OS</b>\n\nВся редакция теперь управляется кнопками. Выбирай раздел:",parse_mode=ParseMode.HTML,reply_markup=main_keyboard())

@router.message(Command("shop"))
async def shop_command(message:Message,state:FSMContext):
    await state.clear()
    if shop_bot and not admin(message):
        me=await shop_bot.get_me()
        return await message.answer("Магазин вынесен в отдельного бота",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть магазин →",url=f"https://t.me/{me.username}?start=direct")]]))
    await message.answer("<b>Витрина глазами клиента</b>",parse_mode=ParseMode.HTML,reply_markup=storefront(settings.gifts_subscription_bot_username))

@router.callback_query(F.data=="shop:home")
async def shop_home(c:CallbackQuery,state:FSMContext):
    await state.clear(); await c.message.edit_text("<b>Выбери результат</b>",parse_mode=ParseMode.HTML,reply_markup=storefront(settings.gifts_subscription_bot_username)); await c.answer()

@router.callback_query(F.data.startswith("shop:category:"))
async def shop_category(c:CallbackQuery):
    category=c.data.rsplit(":",1)[-1]
    if category not in {"liga","services"}: return await c.answer("Раздел не найден",show_alert=True)
    title="Футбольная лаборатория" if category=="liga" else "Digital Lab"
    await c.message.edit_text(f"<b>{title}</b>\n\nВыбирай не красивое название, а проблему, которую надо закрыть",parse_mode=ParseMode.HTML,reply_markup=category_keyboard(category)); await c.answer()

@router.callback_query(F.data.startswith("shop:offer:"))
async def shop_offer(c:CallbackQuery,state:FSMContext):
    key=c.data.rsplit(":",1)[-1]; offer=OFFERS.get(key)
    if not offer: return await c.answer("Услуга не найдена",show_alert=True)
    data=await state.get_data(); track(c.from_user.id,"offer_view",data.get("shop_source","direct"),key)
    await c.message.edit_text(f"<b>{html.escape(offer.title)}</b>\n{html.escape(offer.price)}\n\n{html.escape(offer.description)}\n\nСначала уточним задачу. Оплата — только после согласования объёма",parse_mode=ParseMode.HTML,reply_markup=offer_keyboard(key)); await c.answer()

@router.callback_query(F.data.startswith("shop:order:"))
async def shop_order(c:CallbackQuery,state:FSMContext):
    key=c.data.rsplit(":",1)[-1]
    if key not in OFFERS: return await c.answer("Услуга не найдена",show_alert=True)
    current=await state.get_data(); await state.set_state(ShopState.waiting_brief); await state.update_data(offer_key=key,shop_source=current.get("shop_source","direct"))
    await c.message.edit_text("<b>Одним сообщением:</b> что у тебя сейчас и какой результат хочешь получить?\n\nМожно приложить ссылку на канал, Gift или видео следующим сообщением",parse_mode=ParseMode.HTML,reply_markup=shop_nav(f"shop:offer:{key}")); await c.answer()

@router.callback_query(F.data=="shop:diagnostic")
async def diagnostic_start(c:CallbackQuery,state:FSMContext):
    if db.get(f"free_diagnostic:{c.from_user.id}"): return await c.answer("Ты уже использовал бесплатную диагностику",show_alert=True)
    await state.set_state(ShopState.waiting_diagnostic)
    await c.message.edit_text("🎯 <b>Бесплатная экспресс-диагностика</b>\n\nНачни сообщение со слова <b>Футбол</b>, <b>Контент</b> или <b>Gifts</b>, затем коротко опиши проблему\n\nНапример: <i>Футбол. Теряю место в составе после двух слабых матчей</i>",parse_mode=ParseMode.HTML,reply_markup=shop_nav()); await c.answer()

@router.message(ShopState.waiting_diagnostic)
async def diagnostic_result(message:Message,state:FSMContext):
    brief=(message.text or "").strip(); lower=brief.lower()
    if len(brief)<20 or not any(lower.startswith(x) for x in ("футбол","контент","услуги","gifts","гифт")):
        return await message.answer("Начни с «Футбол», «Контент» или «Gifts» и опиши ситуацию немного подробнее")
    channel="liga" if lower.startswith("футбол") else "gifts"; offer_key="liga_episode" if channel=="liga" else "ai_short"
    wait=await message.answer("🧠 Ищу не очевидный совет, а реальную слабую точку…")
    system=(CHANNELS[channel]["voice"]+"\nТы проводишь бесплатную экспресс-диагностику потенциальному клиенту. "
      "Дай 3 коротких наблюдения: что человек, вероятно, недооценивает; что проверить прямо сейчас; какой следующий шаг. "
      "Не придумывай факты и не обещай результат. 450–650 знаков. Используй максимум один эмодзи. Последняя строка без точки")
    try: result=await editor.llm(system,brief,.65)
    except Exception: result="Проблема понятна, но данных пока мало для честного вывода. Зафиксируй один конкретный эпизод или Gift, решение, которое ты принял, и результат. Тогда станет видно не симптом, а место, где действительно теряется преимущество"
    db.set(f"free_diagnostic:{message.from_user.id}",datetime.now(settings.timezone).isoformat()); await state.clear()
    if lower.startswith(("gifts","гифт")):
        username=settings.gifts_subscription_bot_username or "vsdvscbot"
        next_step=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть Gifts Intelligence →",url=f"https://t.me/{username}?start=shop")]])
    else: next_step=offer_keyboard(offer_key)
    await wait.edit_text(telegram_html(result)+"\n\n<b>Следующий шаг</b>",parse_mode=ParseMode.HTML,reply_markup=next_step)

@router.message(ShopState.waiting_brief)
async def shop_brief(message:Message,state:FSMContext):
    brief=(message.text or message.caption or "").strip()
    if len(brief)<5: return await message.answer("Напиши чуть подробнее — хотя бы одним нормальным предложением")
    data=await state.get_data(); key=data.get("offer_key",""); offer=OFFERS.get(key)
    if not offer: await state.clear(); return await message.answer("Заявка устарела. Открой /shop заново")
    username=(message.from_user.username or "") if message.from_user else ""
    try:
        order_id=db.save_service_order(message.from_user.id,username,key,brief)
    except Exception:
        # Keep the lead alive while an older Supabase schema is still deployed.
        log.exception("Could not persist service order; delivering it to admin directly")
        order_id=f"TG-{message.message_id}"
    admin_chat=db.get("admin_chat_id")
    if admin_chat:
        contact=f"@{username}" if username else f"ID <code>{message.from_user.id}</code>"
        await bot.send_message(int(admin_chat),f"<b>Новая заявка #{order_id}</b>\n\n{html.escape(offer.title)} · {html.escape(offer.price)}\nКлиент: {contact}\n\n{html.escape(brief)}",parse_mode=ParseMode.HTML)
    track(message.from_user.id,"order_created",data.get("shop_source","direct"),key)
    await state.clear()
    await message.answer(f"<b>Заявка #{order_id} принята</b>\n\nНапишем после просмотра задачи. Никакой оплаты вслепую",parse_mode=ParseMode.HTML,reply_markup=storefront(settings.gifts_subscription_bot_username))

@router.message(Command("menu"))
async def dashboard(message:Message,state:FSMContext):
    if not admin(message): return
    await state.clear(); await message.answer("🧠 <b>Главное меню</b>",parse_mode=ParseMode.HTML,reply_markup=main_keyboard())

@router.callback_query(F.data=="panel:home")
async def panel_home(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    await state.clear(); await c.message.edit_text("🧠 <b>Главное меню</b>",parse_mode=ParseMode.HTML,reply_markup=main_keyboard()); await c.answer()

@router.callback_query(F.data=="panel:generate")
async def panel_generate(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    await state.clear(); await c.message.edit_text("Куда бьём?",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="⚽ Лига",callback_data="gen:liga"),InlineKeyboardButton(text="🎁 Gifts",callback_data="gen:gifts")],
      [InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")]])); await c.answer()

@router.callback_query(F.data=="panel:shop")
async def panel_shop(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    await state.clear(); await c.message.edit_text("🛒 <b>Магазин глазами клиента</b>",parse_mode=ParseMode.HTML,reply_markup=storefront(settings.gifts_subscription_bot_username)); await c.answer()

@router.callback_query(F.data=="panel:orders")
async def panel_orders(c:CallbackQuery):
    if not admin(c): return
    try: rows=db.service_orders()
    except Exception: rows=[]
    if not rows:
        await c.answer(); return await c.message.edit_text("📥 Новых заявок пока нет",reply_markup=back_menu())
    lines=["📥 <b>Новые заявки</b>"]; buttons=[]
    for row in rows[:15]:
        offer=OFFERS.get(row["offer_key"]); name=offer.title if offer else row["offer_key"]
        contact=f"@{row['username']}" if row["username"] else ""
        if not contact: contact=f"ID {row['user_id']}"
        lines.append(f"\n<b>#{row['id']} · {html.escape(name)}</b>\n{html.escape(contact)}\n{html.escape(row['brief'][:240])}")
        buttons.append([InlineKeyboardButton(text=f"✅ В работу #{row['id']}",callback_data=f"order:accept:{row['id']}"),InlineKeyboardButton(text="Закрыть",callback_data=f"order:close:{row['id']}")])
        buttons.append([InlineKeyboardButton(text=f"💬 Написать клиенту #{row['id']}",url=f"tg://user?id={row['user_id']}")])
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")])
    await c.message.edit_text("\n".join(lines),parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)); await c.answer()

@router.callback_query(F.data.startswith("order:"))
async def order_status(c:CallbackQuery):
    if not admin(c): return
    _,action,raw_id=c.data.split(":",2)
    if not raw_id.isdigit() or action not in {"accept","close"}: return await c.answer("Некорректная заявка",show_alert=True)
    order=db.service_order(int(raw_id)); status="accepted" if action=="accept" else "closed"; db.update_service_order(int(raw_id),status)
    if order:
        text=(f"✅ <b>Заявка #{raw_id} взята в работу</b>\n\nСкоро напишем с уточнениями и точной стоимостью"
              if action=="accept" else f"🏁 <b>Заявка #{raw_id} закрыта</b>\n\nЕсли понадобится новый разбор — витрина всегда доступна через /shop")
        try: await (shop_bot or bot).send_message(int(order["user_id"]),text,parse_mode=ParseMode.HTML)
        except Exception: log.info("Could not notify customer for order %s",raw_id)
    await panel_orders(c)

@router.callback_query(F.data=="panel:football")
async def panel_football(c:CallbackQuery):
    if not admin(c): return
    await c.message.edit_text("⚽ <b>Футбольная лаборатория</b>",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="📡 Матчи сегодня",callback_data="panel:games"),InlineKeyboardButton(text="🎥 Разобрать видео",callback_data="panel:match")],
      [InlineKeyboardButton(text="🔎 Статус разбора",callback_data="panel:matchhelp"),InlineKeyboardButton(text="🎯 Выбрать игрока",callback_data="panel:targethelp")],
      [InlineKeyboardButton(text="👤 Player Passport",callback_data="panel:players")],
      [InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")]])); await c.answer()

@router.callback_query(F.data=="panel:players")
async def panel_players(c:CallbackQuery):
    if not admin(c): return
    await c.message.edit_text("👤 <b>Player Passport</b>",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="➕ Новый футболист",callback_data="panel:newplayer"),InlineKeyboardButton(text="📚 Все футболисты",callback_data="panel:playerlist")],
      [InlineKeyboardButton(text="🔗 Привязать матч",callback_data="panel:linkhelp"),InlineKeyboardButton(text="📈 Открыть паспорт",callback_data="panel:passporthelp")],
      [InlineKeyboardButton(text="‹ Назад",callback_data="panel:football"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")]])); await c.answer()

@router.callback_query(F.data=="panel:system")
async def panel_system(c:CallbackQuery):
    if not admin(c): return
    await c.message.edit_text("⚙️ <b>Система</b>",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="🟢 Состояние",callback_data="panel:status"),InlineKeyboardButton(text="✨ Premium эмодзи",callback_data="panel:emojihelp")],
      [InlineKeyboardButton(text="📚 База курсов",callback_data="panel:courses")],
      [InlineKeyboardButton(text="🧬 Обновить память",callback_data="panel:sync"),InlineKeyboardButton(text="📊 Аналитика",callback_data="panel:analytics")],
      [InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")]])); await c.answer()

@router.message(Command("playeradd"))
async def player_add(message:Message):
    if not admin(message): return
    raw=(message.text or "").partition(" ")[2]; parts=[part.strip() for part in raw.split("|")]
    if not parts or not parts[0]:
        return await message.answer("Формат: <code>/playeradd Имя | 2009 | правый вингер | правая</code>",parse_mode=ParseMode.HTML)
    birth_year=int(parts[1]) if len(parts)>1 and parts[1].isdigit() else None
    player_id=db.save_player(parts[0],birth_year,parts[2] if len(parts)>2 else "",parts[3] if len(parts)>3 else "")
    await message.answer(f"✅ Player Passport #{player_id} создан для <b>{html.escape(parts[0])}</b>.",parse_mode=ParseMode.HTML)

@router.message(Command("players"))
async def player_list(message:Message):
    if not admin(message): return
    rows=db.players()
    if not rows: return await message.answer("Профилей пока нет. Создать: <code>/playeradd Имя | год | позиция | нога</code>",parse_mode=ParseMode.HTML)
    lines=[f"#{row['id']} · <b>{html.escape(row['display_name'])}</b> · {html.escape(row['position'] or 'позиция не указана')}" for row in rows[:30]]
    buttons=[[InlineKeyboardButton(text=f"📈 {row['display_name']}",callback_data=f"passport:{row['id']}")] for row in rows[:20]]
    buttons.append([InlineKeyboardButton(text="‹ Назад",callback_data="panel:players"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")])
    await message.answer("👤 <b>Player Passports</b>\n\n"+"\n".join(lines),parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.message(Command("playerlink"))
async def player_link(message:Message):
    if not admin(message): return
    parts=(message.text or "").split()
    if len(parts)!=3 or not parts[1].isdigit() or not parts[2].isdigit():
        return await message.answer("Формат: <code>/playerlink ID_ИГРОКА ID_РАЗБОРА</code>",parse_mode=ParseMode.HTML)
    player_id,match_id=map(int,parts[1:]); player,_=db.player_report(player_id); match=db.match_job(match_id)
    if not player or not match: return await message.answer("Не нашёл профиль или разбор.")
    if match["status"]!="completed": return await message.answer("Сначала дождись завершения разбора.")
    db.link_player_match(player_id,match_id); await message.answer("✅ Матч добавлен в Player Passport.")

@router.message(Command("passport"))
async def player_passport(message:Message):
    if not admin(message): return
    parts=(message.text or "").split()
    if len(parts)!=2 or not parts[1].isdigit(): return await message.answer("Формат: <code>/passport ID_ИГРОКА</code>",parse_mode=ParseMode.HTML)
    await show_passport(message,int(parts[1]))

async def show_passport(target,player_id,edit=False):
    player,matches=db.player_report(player_id)
    if not player:
        if edit: return await target.edit_text("Профиль не найден.",reply_markup=admin_nav("panel:players"))
        return await target.answer("Профиль не найден.",reply_markup=admin_nav("panel:players"))
    summary=aggregate_passport(matches)
    if summary:
        zone={"left":"левый фланг","centre":"центр","right":"правый фланг"}[summary["zone"]]
        numbers=(f"\n\n<b>Разборов: {summary['count']}</b> · видео: ≈ {summary['video_minutes']:.0f} мин\n"
                 f"Видимость игрока: ≈ {summary['visibility']:.0f}% · активность в кадре: ≈ {summary['movement']:.1f}\n"
                 f"Чаще появляется: <b>{zone}</b> · выделено эпизодов: {summary['moments']}\n\n"
                 "<i>Это координатная видеоаналитика, не GPS и не официальный event-data</i>")
    else: numbers="\n\nМатчи ещё не привязаны или метрики не готовы."
    text=f"👤 <b>{html.escape(player['display_name'])}</b>\n{html.escape(player['position'] or 'Позиция не указана')} · {player['birth_year'] or 'год не указан'} · {html.escape(player['strong_foot'] or 'нога не указана')}{numbers}"
    markup=admin_nav("panel:players")
    if edit: await target.edit_text(text,parse_mode=ParseMode.HTML,reply_markup=markup)
    else: await target.answer(text,parse_mode=ParseMode.HTML,reply_markup=markup)

@router.callback_query(F.data.startswith("passport:"))
async def passport_button(c:CallbackQuery):
    if not admin(c): return
    raw=c.data.split(":",1)[1]
    if not raw.isdigit(): return await c.answer("Профиль не найден",show_alert=True)
    await c.answer(); await show_passport(c.message,int(raw),edit=True)

@router.message(Command("emoji"))
async def save_premium_emoji(message:Message):
    if not admin(message): return
    parts=(message.text or "").split(maxsplit=2); channel=parts[1].lower() if len(parts)>1 else ""
    if channel not in {"liga","gifts"}: return await message.answer("Пришли премиум-эмодзи вместе с командой:\n<code>/emoji liga ⚡</code> или <code>/emoji gifts 💎</code>",parse_mode=ParseMode.HTML)
    custom={}
    for entity in message.entities or []:
        emoji_id=getattr(entity,"custom_emoji_id",None)
        if emoji_id:
            fallback=entity.extract_from(message.text or "").replace("\ufe0f",""); custom[fallback]=str(emoji_id)
    if not custom: return await message.answer("Я не увидел премиум-эмодзи. Отправь именно custom emoji, не обычный Unicode.")
    existing_raw=db.get(f"premium_emojis:{channel}") or "{}"
    try: existing=json.loads(existing_raw)
    except json.JSONDecodeError: existing={}
    existing.update(custom); db.set(f"premium_emojis:{channel}",json.dumps(existing,ensure_ascii=False))
    await message.answer(f"✅ Сохранил для {channel}: "+" ".join(custom))

@router.message(Command("games"))
async def games(message:Message):
    if not admin(message): return
    wait=await message.answer("📡 Сканирую сегодняшние матчи…")
    try: fixtures=await football.fixtures()
    except Exception as exc: return await wait.edit_text(f"❌ Match Radar: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    rows=fixtures_keyboard_rows(fixtures)
    if not rows: return await wait.edit_text("Сегодня в выбранных турнирах матчей не найдено.")
    keyboard_rows=[[InlineKeyboardButton(text=label,callback_data=f"gamepost:{fixture_id}")] for label,fixture_id in rows]
    keyboard_rows.append([InlineKeyboardButton(text="‹ Назад",callback_data="panel:football"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")])
    await wait.edit_text("⚽ <b>Какой матч вскрываем?</b>\n\nБот возьмёт реальные события и статистику, найдёт один сильный конфликт и соберёт пост.",
                         parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows))

@router.callback_query(F.data.startswith("gamepost:"))
async def game_post(c:CallbackQuery):
    if not admin(c): return
    fixture_id=int(c.data.split(":",1)[1]); await c.answer("Собираю реальные цифры…")
    wait=await c.message.answer("🧠 Ищу, какая цифра врёт о матче громче остальных…")
    try:
        facts=await football.match_facts(fixture_id); draft_id=await editor.create_match_data_post(facts)
        await wait.delete(); await review(draft_id)
    except Exception as exc:
        log.exception("Match Radar failed"); await wait.edit_text(f"❌ Не собрал разбор: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)

@router.message(Command("match"))
async def match_start(message:Message,state:FSMContext):
    if not admin(message): return
    if not matchlens.ready:
        return await message.answer("❌ <b>MatchLens пока недоступен</b>\n\nВ Railway не подключён отдельный сервис анализа видео. Матч не будет принят, пока health-check сервиса не пройдёт",parse_mode=ParseMode.HTML)
    await state.clear(); await state.set_state(MatchState.waiting_source)
    await message.answer("⚽ <b>MatchLens</b>\n\nПришли ссылку на полный матч, тайм или игровой эпизод. Подойдут YouTube и прямая ссылка на файл.",parse_mode=ParseMode.HTML,reply_markup=admin_nav("panel:football"))

@router.message(MatchState.waiting_source)
async def match_source(message:Message,state:FSMContext):
    if not admin(message): return
    media=message.video or message.document
    if media:
        wait=await message.answer("📤 Передаю видео в MatchLens…")
        try: source=await matchlens.upload_telegram(bot,media.file_id,int(media.file_size or 0))
        except Exception as exc: return await wait.edit_text(f"❌ {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
        await wait.delete(); await state.update_data(source_type="telegram",source_ref=source); await state.set_state(MatchState.waiting_player)
        return await message.answer("Кого выделяем? Напиши номер, цвет формы и позицию. Например:\n<code>№7, синяя форма, правый вингер</code>",parse_mode=ParseMode.HTML,reply_markup=admin_nav("panel:match"))
    source=(message.text or "").strip()
    try: MatchRequest("url",source,"проверка").validate()
    except ValueError: return await message.answer("Нужна полная ссылка, начинающаяся с http:// или https://")
    await state.update_data(source_type="url",source_ref=source); await state.set_state(MatchState.waiting_player)
    await message.answer("Кого выделяем? Напиши, например:\n\n<code>№7, синяя форма, правый вингер</code>\nили\n<code>вся команда в белом</code>",parse_mode=ParseMode.HTML,reply_markup=admin_nav("panel:match"))

@router.message(MatchState.waiting_player)
async def match_player(message:Message,state:FSMContext):
    if not admin(message): return
    player=(message.text or "").strip()
    if len(player)<2: return await message.answer("Опиши номер, цвет формы и позицию чуть точнее.")
    await state.update_data(player_ref=player); await state.set_state(MatchState.waiting_mode)
    await message.answer("Что собираем?",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="👤 Только игрок",callback_data="matchmode:player"),InlineKeyboardButton(text="🧩 Команда",callback_data="matchmode:team")],
      [InlineKeyboardButton(text="🔥 Полный разбор",callback_data="matchmode:full")],
      [InlineKeyboardButton(text="‹ Назад",callback_data="panel:match"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")]]))

@router.callback_query(MatchState.waiting_mode,F.data.startswith("matchmode:"))
async def match_submit(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    mode=c.data.split(":",1)[1]; data=await state.get_data(); await state.clear(); await c.answer("Задание принято")
    try:
        local_id,external=await matchlens.submit(MatchRequest(data.get("source_type","url"),data["source_ref"],data["player_ref"],mode))
    except Exception as exc:
        log.exception("MatchLens submit failed"); return await c.message.answer(f"❌ Не удалось передать матч: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    if external:
        text=f"✅ <b>Разбор #{local_id} запущен</b>\n\nИгрок: {html.escape(data['player_ref'])}\nПроверить: <code>/matchstatus {local_id}</code>"
    else:
        text=(f"🧱 <b>Задание #{local_id} сохранено</b>\n\nИгрок: {html.escape(data['player_ref'])}\n"
              "Видеосервис MatchLens ещё не подключён — после его деплоя это задание можно будет отправить в обработку.\n\n"+confidence_legend())
    await c.message.answer(text,parse_mode=ParseMode.HTML,reply_markup=match_job_keyboard(local_id))

async def show_match_status(target,local_id,edit=False):
    row=await matchlens.refresh(local_id); tracker_ids=[]
    try: metrics_raw=row["metrics_json"]
    except (KeyError,IndexError): metrics_raw=None
    if metrics_raw:
        try: tracker_ids=list((json.loads(metrics_raw) or {}).get("players",{}))
        except (TypeError,ValueError): pass
    ids=f"\nНайдены игроки: <code>{html.escape(', '.join(tracker_ids[:24]))}</code>" if tracker_ids else ""
    hint=f"{ids}\n\nНажми на ID своего футболиста ниже" if row["status"]=="awaiting_selection" else ""
    error=f"\nОшибка: {html.escape(row['error'])}" if row["error"] else ""
    text=f"⚽ <b>Разбор #{row['id']}</b>\nСтатус: {html.escape(row['status'])}\nГотовность: {row['progress']}%{hint}{error}"
    profiles=db.players() if row["status"]=="completed" else ()
    markup=match_job_keyboard(row["id"],tracker_ids if row["status"]=="awaiting_selection" else (),row["result_url"] or "",profiles)
    if edit: await target.edit_text(text,parse_mode=ParseMode.HTML,disable_web_page_preview=True,reply_markup=markup)
    else: await target.answer(text,parse_mode=ParseMode.HTML,disable_web_page_preview=True,reply_markup=markup)
    return row

@router.message(Command("matchstatus"))
async def match_status(message:Message):
    if not admin(message): return
    parts=(message.text or "").split(maxsplit=1)
    if len(parts)<2 or not parts[1].isdigit(): return await message.answer("Формат: <code>/matchstatus 1</code>",parse_mode=ParseMode.HTML)
    try: await show_match_status(message,int(parts[1]))
    except Exception as exc: return await message.answer(f"❌ {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("matchrefresh:"))
async def match_refresh_button(c:CallbackQuery):
    if not admin(c): return
    raw=c.data.split(":",1)[1]
    if not raw.isdigit(): return await c.answer("Некорректный разбор",show_alert=True)
    await c.answer("Обновляю…")
    try: await show_match_status(c.message,int(raw),edit=True)
    except Exception as exc: await c.message.answer(f"❌ {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("matchpick:"))
async def match_pick_button(c:CallbackQuery):
    if not admin(c): return
    parts=c.data.split(":")
    if len(parts)!=3 or not parts[1].isdigit() or not parts[2].isdigit(): return await c.answer("Некорректный игрок",show_alert=True)
    await c.answer("Игрок выбран")
    try: await matchlens.select_target(int(parts[1]),int(parts[2]))
    except Exception as exc: return await c.message.answer(f"❌ {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    await c.message.edit_text(f"✅ <b>Игрок #{parts[2]} выбран</b>\n\nФинальный отчёт собирается",parse_mode=ParseMode.HTML,reply_markup=match_job_keyboard(int(parts[1])))

@router.callback_query(F.data.startswith("matchlink:"))
async def match_link_button(c:CallbackQuery):
    if not admin(c): return
    parts=c.data.split(":")
    if len(parts)!=3 or not parts[1].isdigit() or not parts[2].isdigit(): return await c.answer("Некорректная привязка",show_alert=True)
    player, _=db.player_report(int(parts[2])); match=db.match_job(int(parts[1]))
    if not player or not match or match["status"]!="completed": return await c.answer("Профиль или готовый разбор не найден",show_alert=True)
    db.link_player_match(int(parts[2]),int(parts[1])); await c.answer("Добавлено в Player Passport",show_alert=True)

@router.message(Command("matchplayer"))
async def match_player_select(message:Message):
    if not admin(message): return
    parts=(message.text or "").split()
    if len(parts)!=3 or not parts[1].isdigit() or not parts[2].isdigit():
        return await message.answer("Формат: <code>/matchplayer ID_РАЗБОРА ID_ИГРОКА</code>\nНапример: <code>/matchplayer 3 7</code>",parse_mode=ParseMode.HTML)
    try: await matchlens.select_target(int(parts[1]),int(parts[2]))
    except Exception as exc: return await message.answer(f"❌ {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    await message.answer(f"✅ Игрок #{parts[2]} выбран. Финальный отчёт собирается.\nПроверить: <code>/matchstatus {parts[1]}</code>",parse_mode=ParseMode.HTML)

@router.message(Command("analytics"))
async def analytics_report(message:Message):
    if not admin(message): return
    wait=await message.answer("📊 Обновляю просмотры, реакции и пересылки…")
    result=await analytics.sync(); report=analytics.report()
    await wait.edit_text(f"{report}\n\nОбновлено: {result['updated']} · Ошибок: {len(result['errors'])}")

@router.message(Command("giftpost"))
async def gift_data_post(message:Message):
    if not admin(message): return
    wait=await message.answer("🛰 Снимаю рынок: объёмы, greed, health и наши сигналы…")
    try:
        snapshot=await gifts_data.snapshot(); facts=gifts_data.editorial_facts(snapshot)
        if facts:
            draft_id=await editor.create_gifts_data_post(facts)
            await wait.edit_text(f"✅ Рыночный срез собран. Ошибок источников: {len(snapshot['errors'])}")
        else:
            draft_id=await editor.create("gifts")
            reason="; ".join(snapshot["errors"][:2]) or "API вернул пустые данные"
            await wait.edit_text("⚠️ Рыночный API сейчас недоступен, поэтому сделал честный Gifts-разбор без цен.\n\n"+html.escape(reason[:500]),parse_mode=ParseMode.HTML)
        await review(draft_id)
    except Exception as exc:
        log.exception("Gifts Data Desk failed"); await wait.edit_text(f"❌ Data Desk: {html.escape(str(exc)[:400])}",parse_mode=ParseMode.HTML)

@router.message(Command("sync"))
async def sync_history(message:Message):
    if not admin(message): return
    wait=await message.answer("🧬 Читаю последние посты и обновляю память…")
    results=await history.sync_all(); lines=[]
    for item in results:
        mark="❌" if item.error else "✅"
        detail=item.error if item.error else f"найдено {item.found}, новых {item.added}"
        lines.append(f"{mark} @{item.channel} · {item.role}: {detail}")
    await wait.edit_text("<b>Синхронизация завершена</b>\n\n"+"\n".join(lines),parse_mode=ParseMode.HTML)

@router.message(Command("coursesync"))
async def course_sync(message:Message):
    if not admin(message): return
    wait=await message.answer("📚 Читаю только разрешённые каналы курсов…")
    try: results=await history.sync_courses()
    except Exception as exc: return await wait.edit_text(f"❌ {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    lines=[f"{'❌' if x.error else '✅'} {html.escape(x.channel)}: найдено {x.found}, новых {x.added}{' · '+html.escape(x.error) if x.error else ''}" for x in results]
    await wait.edit_text("📚 <b>База курсов обновлена</b>\n\n"+"\n".join(lines),parse_mode=ParseMode.HTML)

@router.message(Command("coursepost"))
async def course_post(message:Message):
    if not admin(message): return
    parts=(message.text or "").split(); channel=parts[1].lower() if len(parts)>1 else "gifts"
    if channel not in {"liga","gifts"}: return await message.answer("Формат: <code>/coursepost gifts</code> или <code>/coursepost liga</code>",parse_mode=ParseMode.HTML)
    wait=await message.answer("🧠 Превращаю принцип из курсов в оригинальный пост…")
    try: draft_id=await editor.create_from_courses(channel)
    except Exception as exc: return await wait.edit_text(f"❌ {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    await wait.delete(); await review(draft_id)

@router.message(Command("generate"))
async def menu(message:Message,state:FSMContext):
    if not admin(message): return
    await state.clear()
    await message.answer("Куда бьём?",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
      InlineKeyboardButton(text="⚽ Лига",callback_data="gen:liga"),InlineKeyboardButton(text="🎁 Gifts",callback_data="gen:gifts")]]))

@router.callback_query(F.data.startswith("gen:"))
async def gen_cb(c:CallbackQuery):
    if not admin(c): return
    channel=c.data.split(":")[1]
    await c.message.edit_text("Как собираем пост?",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="⚡ Авто: свежий заход",callback_data=f"genmode:{channel}:auto")],
      [InlineKeyboardButton(text="✍️ Напишу тему",callback_data=f"genmode:{channel}:topic"),InlineKeyboardButton(text="🔗 Из статьи",callback_data=f"genmode:{channel}:url")],
      [InlineKeyboardButton(text="🎞 Фирменная серия",callback_data=f"genmode:{channel}:series")],
      [InlineKeyboardButton(text="‹ Назад",callback_data="panel:generate"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")]])); await c.answer()

def rubric_keyboard(channel):
    labels={"короткий_удар":"⚡ Короткий удар","история":"🎭 История","антисистема":"🥊 Антисистема","разбор":"🔬 Разбор","тренировка":"🏋️ Тренировка",
            "новость":"⚡ Новость","рынок_за_минуту":"📊 Рынок","разбор_ошибки":"🧨 Разбор ошибки","обучение":"🧠 Обучение",
            "сигнал_или_шум":"📡 Сигнал/шум","мем":"😏 Мем"}
    rows=[[InlineKeyboardButton(text=labels.get(fmt,fmt.replace("_"," ").title()),callback_data=f"rubric:{fmt}")]
      for fmt in CHANNELS[channel]["formats"]]
    rows.append([InlineKeyboardButton(text="‹ Назад",callback_data=f"gen:{channel}"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(F.data.startswith("genmode:"))
async def generation_mode(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    _,channel,mode=c.data.split(":",2)
    if mode=="auto":
        await c.answer("Редакция ищет сильный заход…"); return await generate(channel)
    if mode=="series":
        rows=[[InlineKeyboardButton(text=f"{name}",callback_data=f"series:{channel}:{key}"),
               InlineKeyboardButton(text="Сезон ×3",callback_data=f"seriespack:{channel}:{key}")]
              for key,(name,_,_) in SERIES[channel].items()]
        rows.append([InlineKeyboardButton(text="‹ Назад",callback_data=f"gen:{channel}"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")])
        await c.message.edit_text("Выбирай сериал — бот сохранит его характер:",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)); return await c.answer()
    await state.update_data(channel=channel)
    if mode=="topic":
        await state.set_state(GenerateState.waiting_topic); await c.message.answer("Напиши тему, мысль или сырой набросок. Можно одной фразой — я докручу заход, но факты выдумывать не буду.",reply_markup=admin_nav(f"gen:{channel}"))
    else:
        await state.set_state(GenerateState.waiting_url); await c.message.answer("Пришли ссылку на статью или страницу. Я вытащу смысл, а ссылку и источник в пост не поставлю.",reply_markup=admin_nav(f"gen:{channel}"))
    await c.answer()

@router.message(GenerateState.waiting_topic)
async def own_topic(message:Message,state:FSMContext):
    if not admin(message): return
    brief=(message.text or "").strip()
    if len(brief)<3: return await message.answer("Напиши тему чуть подробнее.")
    data=await state.get_data(); await state.update_data(brief=brief,title="Своя тема",url=""); await state.set_state(GenerateState.waiting_rubric)
    await message.answer("В какую рубрику упаковать?",reply_markup=rubric_keyboard(data["channel"]))

@router.message(GenerateState.waiting_url)
async def article_url(message:Message,state:FSMContext):
    if not admin(message): return
    wait=await message.answer("🔎 Читаю материал и отделяю факты от воды…")
    try: title,brief,url=await fetch_article((message.text or "").strip())
    except Exception as exc: return await wait.edit_text(f"Не смог прочитать страницу: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    if len(brief)<120: return await wait.edit_text("На странице слишком мало читаемого текста. Пришли другую ссылку или выбери «Напишу тему».")
    data=await state.get_data(); await state.update_data(brief=brief,title=title,url=url); await state.set_state(GenerateState.waiting_rubric)
    await wait.edit_text(f"✅ Материал прочитан: <b>{html.escape(title[:120])}</b>\n\nТеперь выбери рубрику.",parse_mode=ParseMode.HTML,reply_markup=rubric_keyboard(data["channel"]))

@router.callback_query(GenerateState.waiting_rubric,F.data.startswith("rubric:"))
async def rubric_selected(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    fmt=c.data.split(":",1)[1]; data=await state.get_data(); channel=data["channel"]
    if fmt not in CHANNELS[channel]["formats"]: return await c.answer("Неизвестная рубрика",show_alert=True)
    await c.answer("Собираю пост…")
    try: draft_id=await editor.create_from_brief(channel,fmt,data["brief"],data.get("title","Своя тема"),data.get("url",""))
    except Exception as exc: log.exception("Brief generation failed"); return await c.message.answer(f"❌ Не собрал пост: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    await state.clear(); await review(draft_id)

@router.callback_query(F.data.startswith("series:"))
async def series_selected(c:CallbackQuery):
    if not admin(c): return
    _,channel,key=c.data.split(":",2)
    if channel not in SERIES or key not in SERIES[channel]: return await c.answer("Серия не найдена",show_alert=True)
    name,fmt,brief=SERIES[channel][key]; await c.answer("Собираю новый выпуск…")
    try: draft_id=await editor.create_from_brief(channel,fmt,f"Серия «{name}». {brief}",name)
    except Exception as exc: log.exception("Series generation failed"); return await c.message.answer(f"❌ Не собрал выпуск: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    await review(draft_id)

@router.callback_query(F.data.startswith("seriespack:"))
async def series_pack(c:CallbackQuery):
    if not admin(c): return
    _,channel,key=c.data.split(":",2)
    if channel not in SERIES or key not in SERIES[channel]: return await c.answer("Серия не найдена",show_alert=True)
    name,fmt,brief=SERIES[channel][key]; await c.answer("Собираю сезон из трёх выпусков…")
    wait=await c.message.answer(f"🎞 <b>{html.escape(name)} · сезон ×3</b>\n\nСоздаю три разных захода без повторов…",parse_mode=ParseMode.HTML)
    arcs=[
      (fmt,"Выпуск 1/3. Основной выпуск: открой конфликт и сломай привычное убеждение. Не раскрывай всё сразу."),
      ("мем","Выпуск 2/3. Мем-пауза: покажи ту же проблему как узнаваемую сцену и закончи панчем. Не пересказывай первый выпуск."),
      ("короткий_удар","Выпуск 3/3. Короткий финал: дай практический выход или жёсткий выбор. Заверши сезон сильнее, чем начал."),
    ]; created=[]
    try:
        for index,(episode_format,arc) in enumerate(arcs,1):
            draft_id=await editor.create_from_brief(channel,episode_format,f"Серия «{name}». {brief}\n{arc}",f"{name} · {index}/3")
            created.append(draft_id); await wait.edit_text(f"🎞 <b>{html.escape(name)}</b>\n\nГотово {index}/3",parse_mode=ParseMode.HTML)
    except Exception as exc:
        log.exception("Series pack failed"); return await wait.edit_text(f"⚠️ Создано {len(created)}/3. Ошибка: {html.escape(str(exc)[:240])}",parse_mode=ParseMode.HTML)
    pack=",".join(str(x) for x in created)
    await wait.edit_text(f"✅ <b>Сезон готов</b>\n\nЧерновики: {', '.join('#'+str(x) for x in created)}\nКаждый выпуск пришёл отдельной карточкой",parse_mode=ParseMode.HTML,
      reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📅 Расставить на 3 дня",callback_data=f"schedulepack:{pack}")]]))
    for draft_id in created: await review(draft_id)

@router.callback_query(F.data.startswith("schedulepack:"))
async def schedule_pack(c:CallbackQuery):
    if not admin(c): return
    raw=c.data.split(":",1)[1]; ids=[int(x) for x in raw.split(",") if x.isdigit()][:7]
    drafts=[db.draft(x) for x in ids]
    if not drafts or any(not x or x["status"]!="review" for x in drafts): return await c.answer("Часть выпусков уже опубликована или запланирована",show_alert=True)
    channel=drafts[0]["channel_key"]; hour,minute=map(int,settings.schedules[channel][0].split(":")); now=datetime.now(settings.timezone)
    dates=[]
    for offset,(draft_id,draft) in enumerate(zip(ids,drafts),1):
        when=(now+timedelta(days=offset)).replace(hour=hour,minute=minute,second=0,microsecond=0)
        db.update(draft_id,status="scheduled",scheduled_at=when.isoformat()); dates.append(f"#{draft_id} · {when:%d.%m %H:%M}")
    await c.message.edit_text("📅 <b>Сезон поставлен в очередь</b>\n\n"+"\n".join(dates),parse_mode=ParseMode.HTML,reply_markup=back_menu()); await c.answer("Готово")

@router.callback_query(F.data.startswith("publish:"))
async def pub_cb(c:CallbackQuery):
    if not admin(c): return
    await c.answer("Публикую…")
    try: mode,error=await publish(int(c.data.split(":")[1]))
    except Exception as exc:
        log.exception("Publish callback failed")
        return await c.message.answer(f"❌ Не опубликовано: <code>{html.escape(type(exc).__name__+': '+str(exc)[:260])}</code>",parse_mode=ParseMode.HTML)
    await c.message.edit_reply_markup(reply_markup=None)
    if error:
        await c.message.answer(f"⚠️ Пост опубликован через Bot API без Premium\nПричина MTProto: <code>{html.escape(error)}</code>",parse_mode=ParseMode.HTML)
    else: await c.message.answer("✅ Опубликовано через Premium-аккаунт" if mode=="premium" else "✅ Опубликовано через Bot API")

@router.callback_query(F.data.startswith(("harder:","rewrite:","short:")))
async def rewrite_cb(c:CallbackQuery):
    if not admin(c): return
    mode,draft_id=c.data.split(":"); draft_id=int(draft_id); await c.answer("Переписываю…")
    text,score=await editor.rewrite(db.draft(draft_id),mode); db.update(draft_id,text=text,hook_score=score)
    channel_key=db.draft(draft_id)["channel_key"]
    await c.message.edit_text(f"📝 <b>Черновик #{draft_id} · хук {score}/5</b>\n\n{render(channel_key,text)}",parse_mode=ParseMode.HTML,reply_markup=keyboard(draft_id))

def schedule_keyboard(draft_id):
    now=datetime.now(settings.timezone); slots=[]
    for day_offset,hour,minute,label in [(0,18,0,"Сегодня 18:00"),(0,20,30,"Сегодня 20:30"),(0,22,0,"Сегодня 22:00"),
                                          (1,9,0,"Завтра 09:00"),(1,12,0,"Завтра 12:00"),(1,18,0,"Завтра 18:00")]:
        moment=(now+timedelta(days=day_offset)).replace(hour=hour,minute=minute,second=0,microsecond=0)
        if moment>now: slots.append((label,moment))
    rows=[[InlineKeyboardButton(text=label,callback_data=f"at:{draft_id}:{int(moment.timestamp())}")] for label,moment in slots[:5]]
    rows.append([InlineKeyboardButton(text="✍️ Своя дата и время",callback_data=f"customat:{draft_id}")])
    rows.append([InlineKeyboardButton(text="↩️ Назад",callback_data=f"back:{draft_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(F.data.startswith("schedule:"))
async def schedule_menu(c:CallbackQuery):
    if not admin(c): return
    draft_id=int(c.data.split(":")[1]); await c.message.edit_reply_markup(reply_markup=schedule_keyboard(draft_id)); await c.answer("Выбери слот")

@router.callback_query(F.data.startswith("at:"))
async def schedule_at(c:CallbackQuery):
    if not admin(c): return
    _,raw_id,raw_ts=c.data.split(":"); draft_id=int(raw_id); when=datetime.fromtimestamp(int(raw_ts),settings.timezone)
    if when<=datetime.now(settings.timezone): return await c.answer("Этот слот уже прошёл",show_alert=True)
    db.update(draft_id,status="scheduled",scheduled_at=when.isoformat())
    await c.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отменить публикацию",callback_data=f"unschedule:{draft_id}")]]))
    await c.answer(f"Поставлено на {when:%d.%m %H:%M}",show_alert=True)

@router.callback_query(F.data.startswith("customat:"))
async def custom_schedule(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    draft_id=int(c.data.split(":")[1]); await state.set_state(ScheduleState.waiting_datetime); await state.update_data(draft_id=draft_id)
    await c.message.answer("Напиши дату и время по Екатеринбургу:\n<code>03.09 14:35</code>",parse_mode=ParseMode.HTML,reply_markup=admin_nav(f"back:{draft_id}")); await c.answer()

@router.message(ScheduleState.waiting_datetime)
async def custom_schedule_value(message:Message,state:FSMContext):
    if not admin(message): return
    try:
        value=datetime.strptime(message.text.strip(),"%d.%m %H:%M").replace(year=datetime.now(settings.timezone).year,tzinfo=settings.timezone)
        if value<=datetime.now(settings.timezone): raise ValueError
    except (ValueError,AttributeError):
        return await message.answer("Не понял время. Пример: <code>03.09 14:35</code>",parse_mode=ParseMode.HTML)
    data=await state.get_data(); db.update(data["draft_id"],status="scheduled",scheduled_at=value.isoformat()); await state.clear()
    await message.answer(f"⏰ Пост #{data['draft_id']} поставлен на {value:%d.%m в %H:%M}.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
      InlineKeyboardButton(text="❌ Отменить публикацию",callback_data=f"unschedule:{data['draft_id']}")]]))

@router.message(Command("scheduled"))
async def scheduled_posts(message:Message):
    if not admin(message): return
    rows=db.future_scheduled(datetime.now(settings.timezone).isoformat())
    if not rows: return await message.answer("Очередь пуста — запланированных публикаций нет.")
    lines=["⏰ <b>Очередь публикаций</b>"]
    buttons=[]
    for draft in rows:
        when=datetime.fromisoformat(draft["scheduled_at"]).astimezone(settings.timezone)
        lines.append(f"\n#{draft['id']} · {CHANNELS[draft['channel_key']]['emoji']} {when:%d.%m %H:%M} · {html.escape(draft['format_key'])}")
        buttons.append([InlineKeyboardButton(text=f"❌ Отменить #{draft['id']} · {when:%d.%m %H:%M}",callback_data=f"unschedule:{draft['id']}")])
    await message.answer("".join(lines),parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("unschedule:"))
async def unschedule(c:CallbackQuery):
    if not admin(c): return
    draft_id=int(c.data.split(":",1)[1]); draft=db.draft(draft_id)
    if not draft or draft["status"]!="scheduled": return await c.answer("Этот пост уже не стоит в очереди",show_alert=True)
    db.update(draft_id,status="review",scheduled_at=None); await c.answer("Публикация отменена",show_alert=True)
    await c.message.edit_reply_markup(reply_markup=None)
    await c.message.answer(f"↩️ Пост #{draft_id} снят с расписания и возвращён в черновики.",reply_markup=keyboard(draft_id))

@router.callback_query(F.data.startswith("back:"))
async def back_to_draft(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    await state.clear(); draft_id=int(c.data.split(":")[1]); await c.message.edit_reply_markup(reply_markup=keyboard(draft_id)); await c.answer()

@router.callback_query(F.data.startswith("delete:"))
async def delete(c:CallbackQuery):
    if not admin(c): return
    db.update(int(c.data.split(":")[1]),status="deleted"); await c.message.edit_reply_markup(reply_markup=None); await c.answer("Удалено")

@router.callback_query(F.data.startswith("shorts:"))
async def create_shorts(c:CallbackQuery):
    if not admin(c): return
    draft_id=int(c.data.split(":")[1]); await c.answer("Собираю хук, озвучку и сцены…")
    try:
        job_id,data,_,_=await videos.create(db.draft(draft_id))
        if not settings.mpt_base_url:
            return await c.message.answer("🎬 Сценарий готов, но отдельный Shorts Worker ещё не подключён. После его развёртывания здесь будет приходить готовый MP4 — технический JSON больше не показываю.")
        status=await c.message.answer("🎬 <b>Собираю Shorts: 0%</b>\nПодбираю кадры, озвучку и субтитры…",parse_mode=ParseMode.HTML)
        async def progress(value):
            try: await status.edit_text(f"🎬 <b>Собираю Shorts: {value}%</b>\nПодбираю кадры, озвучку и субтитры…",parse_mode=ParseMode.HTML)
            except Exception: pass
        _,video=await videos.render(data,progress)
        await status.delete()
        await bot.send_video(c.message.chat.id,BufferedInputFile(video,filename=f"shorts-{job_id}.mp4"),caption=f"🎬 {data['title']}\n\n{data['caption']}",supports_streaming=True)
    except Exception as exc:
        log.exception("Shorts generation failed"); await c.message.answer(f"❌ Shorts не собрался: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)

@router.message(Command("status"))
async def status(message:Message):
    if not admin(message): return
    counts="\n".join(f"@{r['source_channel']} ({r['source_role']}): {r['count']}" for r in db.import_counts()) or "история ещё не загружена"
    health=await premium_health()
    await message.answer(f"AI: {'готов' if settings.llm_key else 'нет ключа'}\n⚽ {settings.channels['liga']}\n🎁 {settings.channels['gifts']}\n🎥 MatchLens: {'готов' if matchlens.ready else 'НЕ РАБОТАЕТ — нет видеосервиса'}\n📡 Match Radar: {'готов' if football.ready else 'нет API-ключа'}\n🛒 Магазин: {html.escape(shop_health())}\n\n<b>Проверка Premium-публикации:</b>\n{html.escape(health)}\nАвтопубликация: {'да' if settings.auto_publish else 'нет'}\n\n<b>Память:</b>\n{counts}",parse_mode=ParseMode.HTML)

@router.callback_query(F.data=="panel:games")
async def panel_games(c:CallbackQuery):
    if not admin(c): return
    await c.answer("Сканирую матчи…"); wait=await c.message.answer("📡 Сканирую сегодняшние матчи…")
    try: fixtures=await football.fixtures()
    except Exception as exc: return await wait.edit_text(f"❌ Match Radar: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML,reply_markup=admin_nav("panel:football"))
    rows=fixtures_keyboard_rows(fixtures)
    if not rows: return await wait.edit_text("Сегодня в выбранных турнирах матчей не найдено.",reply_markup=admin_nav("panel:football"))
    buttons=[[InlineKeyboardButton(text=label,callback_data=f"gamepost:{fixture_id}")] for label,fixture_id in rows]
    buttons.append([InlineKeyboardButton(text="‹ Назад",callback_data="panel:football"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")])
    await wait.edit_text("⚽ <b>Какой матч вскрываем?</b>\n\nВозьму реальные события и статистику.",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data=="panel:match")
async def panel_match(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    if not matchlens.ready:
        await c.answer("MatchLens не подключён",show_alert=True)
        return await c.message.answer("❌ Анализ видео пока выключен: отдельный MatchLens-сервис не подключён",reply_markup=admin_nav("panel:football"))
    await state.clear(); await state.set_state(MatchState.waiting_source); await c.answer()
    await c.message.answer("⚽ <b>MatchLens</b>\n\nПришли видео из Telegram, ссылку на YouTube или прямую ссылку на файл.",parse_mode=ParseMode.HTML,reply_markup=admin_nav("panel:football"))

@router.callback_query(F.data=="panel:gifts")
async def panel_gifts(c:CallbackQuery):
    if not admin(c): return
    await c.answer("Снимаю рынок…"); wait=await c.message.answer("🛰 Снимаю рынок: объёмы, greed, health и сигналы…")
    try:
        snapshot=await gifts_data.snapshot(); facts=gifts_data.editorial_facts(snapshot)
        if facts:
            draft_id=await editor.create_gifts_data_post(facts); await wait.edit_text(f"✅ Рыночный срез собран. Ошибок источников: {len(snapshot['errors'])}")
        else:
            draft_id=await editor.create("gifts"); await wait.edit_text("⚠️ Рыночные API недоступны: собрал честный Gifts-разбор без выдуманных цен.")
        await review(draft_id)
    except Exception as exc: log.exception("Gifts panel failed"); await wait.edit_text(f"❌ Data Desk: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML,reply_markup=back_menu())

@router.callback_query(F.data=="panel:scheduled")
async def panel_scheduled(c:CallbackQuery):
    if not admin(c): return
    rows=db.future_scheduled(datetime.now(settings.timezone).isoformat()); await c.answer()
    if not rows: return await c.message.edit_text("Очередь пуста — запланированных публикаций нет.",reply_markup=back_menu())
    lines=["⏰ <b>Очередь публикаций</b>"]; buttons=[]
    for draft in rows:
        when=datetime.fromisoformat(draft["scheduled_at"]).astimezone(settings.timezone)
        lines.append(f"\n#{draft['id']} · {CHANNELS[draft['channel_key']]['emoji']} {when:%d.%m %H:%M} · {html.escape(draft['format_key'])}")
        buttons.append([InlineKeyboardButton(text=f"❌ Отменить #{draft['id']} · {when:%d.%m %H:%M}",callback_data=f"unschedule:{draft['id']}")])
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")])
    await c.message.edit_text("".join(lines),parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data=="panel:sync")
async def panel_sync(c:CallbackQuery):
    if not admin(c): return
    await c.answer("Обновляю память…"); wait=await c.message.answer("🧬 Читаю последние посты…")
    results=await history.sync_all(); lines=[]
    for item in results:
        detail=item.error if item.error else f"найдено {item.found}, новых {item.added}"
        lines.append(f"{'❌' if item.error else '✅'} @{item.channel}: {detail}")
    await wait.edit_text("<b>Память обновлена</b>\n\n"+"\n".join(lines),parse_mode=ParseMode.HTML,reply_markup=back_menu())

@router.callback_query(F.data=="panel:analytics")
async def panel_analytics(c:CallbackQuery):
    if not admin(c): return
    await c.answer("Обновляю показатели…"); wait=await c.message.answer("📊 Обновляю просмотры, реакции и пересылки…")
    result=await analytics.sync(); await wait.edit_text(f"{analytics.report()}\n\nОбновлено: {result['updated']} · Ошибок: {len(result['errors'])}",reply_markup=back_menu())

@router.callback_query(F.data=="panel:funnel")
async def panel_funnel(c:CallbackQuery):
    if not admin(c): return
    try: report=summarize_funnel(db.funnel_events())
    except Exception: report=summarize_funnel([])
    sources="\n".join(f"• {html.escape(key)}: {value}" for key,value in report["sources"].most_common()) or "переходов пока нет"
    offers="\n".join(f"• {html.escape(OFFERS[key].title if key in OFFERS else key)}: {value}" for key,value in report["offers"].most_common()) or "заявок пока нет"
    text=(f"🎯 <b>Воронка продаж</b>\n\nПереходы: <b>{report['landings']}</b>\nОткрытия услуг: <b>{report['offer_views']}</b>\n"
          f"Заявки: <b>{report['orders']}</b>\nКонверсия переход → заявка: <b>{report['conversion']}%</b>\n\n<b>Источники</b>\n{sources}\n\n<b>Что покупают</b>\n{offers}")
    await c.message.edit_text(text,parse_mode=ParseMode.HTML,reply_markup=back_menu()); await c.answer()

@router.callback_query(F.data=="panel:status")
async def panel_status(c:CallbackQuery):
    if not admin(c): return
    await c.answer("Проверяю реальные подключения…")
    counts="\n".join(f"@{r['source_channel']}: {r['count']}" for r in db.import_counts()) or "история ещё не загружена"
    health=await premium_health()
    text=(f"🟢 <b>Состояние системы</b>\n\nAI: {'готов' if settings.llm_key else 'нет ключа'}\n"
          f"🎥 MatchLens: {'готов' if matchlens.ready else 'не подключён'}\n📡 Match Radar: {'готов' if football.ready else 'нет API-ключа'}\n🛒 Магазин: {html.escape(shop_health())}\n"
          f"🧬 Полный Telegram-парсер: {'готов' if history.mtproto_ready else 'публичный режим'}\n✨ <b>Premium:</b>\n{html.escape(health)}\n🎬 Shorts: {'настроен, но требует теста' if settings.mpt_base_url else 'не подключён'}\n"
          f"Автопубликация: {'да' if settings.auto_publish else 'нет'}\n\n<b>Память:</b>\n{counts}")
    await c.message.edit_text(text,parse_mode=ParseMode.HTML,reply_markup=back_menu())

@router.callback_query(F.data=="panel:courses")
async def panel_courses(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    await state.clear()
    buttons=[
      [InlineKeyboardButton(text="🔄 Загрузить новые уроки",callback_data="panel:coursesync")],
      [InlineKeyboardButton(text="📎 Добавить PDF / DOCX / TXT",callback_data="panel:coursefile")],
      [InlineKeyboardButton(text="🎁 Пост для Gifts",callback_data="coursemake:gifts"),InlineKeyboardButton(text="⚽ Пост для Лиги",callback_data="coursemake:liga")],
      [InlineKeyboardButton(text="‹ Назад",callback_data="panel:system"),InlineKeyboardButton(text="🏠 Главное меню",callback_data="panel:home")]]
    await c.message.edit_text("📚 <b>Course Intelligence</b>\n\nЧитает только каналы из COURSE_CHANNELS, извлекает идеи и никогда не указывает курс в посте",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)); await c.answer()

@router.callback_query(F.data=="panel:coursefile")
async def panel_course_file(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    await state.set_state(CourseFileState.waiting_file); await c.answer()
    await c.message.answer("📎 Пришли один файл курса: PDF, DOCX, TXT, MD, SRT или VTT — до 20 МБ. Я извлеку только текст и добавлю его в базу знаний",reply_markup=admin_nav("panel:courses"))

@router.message(CourseFileState.waiting_file,F.document)
async def import_course_file(message:Message,state:FSMContext):
    if not admin(message): return
    document=message.document; size=int(document.file_size or 0)
    if size>20*1024*1024: return await message.answer("Файл больше 20 МБ. Раздели его на части или пришли текстовую версию")
    wait=await message.answer("🧠 Извлекаю текст и режу на смысловые части…")
    try:
        buffer=io.BytesIO(); await bot.download(document.file_id,destination=buffer)
        text=extract_course_text(document.file_name or "course.txt",buffer.getvalue()); chunks=course_chunks(text)
        source=f"upload:{(document.file_name or 'course')[:180]}"; added=0
        for index,chunk in enumerate(chunks):
            added+=db.save_course_note(source,message.message_id*1000+index,chunk,message.date.isoformat() if message.date else None)
        await state.clear(); await wait.edit_text(f"✅ <b>Курс добавлен</b>\n\nИзвлечено: {len(text):,} знаков\nСохранено частей: {added}/{len(chunks)}",parse_mode=ParseMode.HTML,reply_markup=back_menu())
    except Exception as exc:
        await wait.edit_text(f"❌ Не прочитал файл: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)

@router.message(CourseFileState.waiting_file)
async def import_course_file_invalid(message:Message):
    if admin(message): await message.answer("Нужен именно файл PDF, DOCX, TXT, MD, SRT или VTT")

@router.callback_query(F.data=="panel:coursesync")
async def panel_course_sync(c:CallbackQuery):
    if not admin(c): return
    await c.answer("Обновляю базу…"); wait=await c.message.answer("📚 Читаю разрешённые каналы…")
    try: results=await history.sync_courses()
    except Exception as exc: return await wait.edit_text(f"❌ {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    await wait.edit_text("📚 Готово\n\n"+"\n".join(f"{x.channel}: +{x.added}" for x in results),reply_markup=back_menu())

@router.callback_query(F.data.startswith("coursemake:"))
async def panel_course_make(c:CallbackQuery):
    if not admin(c): return
    channel=c.data.split(":",1)[1]; await c.answer("Собираю оригинальный пост…")
    try: draft_id=await editor.create_from_courses(channel)
    except Exception as exc: return await c.message.answer(f"❌ {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
    await review(draft_id)

@router.callback_query(F.data.in_({"panel:shorts","panel:matchhelp","panel:targethelp","panel:newplayer","panel:linkhelp","panel:passporthelp","panel:emojihelp"}))
async def panel_help(c:CallbackQuery):
    if not admin(c): return
    help_text={
      "panel:shorts":"🎬 <b>Shorts</b>\n\nСначала создай любой пост. Под готовым черновиком нажми <b>🎬 Shorts</b> — бот пришлёт MP4.",
      "panel:matchhelp":"🔎 Проверить разбор:\n<code>/matchstatus ID</code>\n\nНапример: <code>/matchstatus 3</code>",
      "panel:targethelp":"🎯 Выбрать игрока на превью:\n<code>/matchplayer ID_РАЗБОРА ID_ТРЕКА</code>",
      "panel:newplayer":"➕ Создать футболиста:\n<code>/playeradd Имя | 2009 | правый вингер | правая</code>",
      "panel:linkhelp":"🔗 Добавить готовый разбор в паспорт:\n<code>/playerlink ID_ИГРОКА ID_РАЗБОРА</code>",
      "panel:passporthelp":"📈 Открыть статистику:\n<code>/passport ID_ИГРОКА</code>",
      "panel:emojihelp":"✨ Пришли Premium-эмодзи вместе с командой:\n<code>/emoji liga ⚡</code> или <code>/emoji gifts 💎</code>",
    }
    await c.message.answer(help_text[c.data],parse_mode=ParseMode.HTML,reply_markup=back_menu()); await c.answer()

@router.callback_query(F.data=="panel:playerlist")
async def panel_player_list(c:CallbackQuery):
    if not admin(c): return
    rows=db.players(); await c.answer()
    if not rows: return await c.message.answer("Профилей пока нет.",reply_markup=back_menu())
    lines=[f"#{row['id']} · <b>{html.escape(row['display_name'])}</b> · {html.escape(row['position'] or 'позиция не указана')}" for row in rows[:30]]
    await c.message.answer("👤 <b>Player Passports</b>\n\n"+"\n".join(lines),parse_mode=ParseMode.HTML,reply_markup=back_menu())

async def due():
    for draft in db.scheduled(datetime.now(settings.timezone).isoformat()):
        try: await publish(draft["id"])
        except Exception: log.exception("Publish failed: %s",draft["id"])

async def main():
    db.init(); scheduler=AsyncIOScheduler(timezone=settings.timezone)
    await bot.set_my_commands([BotCommand(command="start",description="главное меню"),BotCommand(command="menu",description="главное меню"),BotCommand(command="generate",description="создать пост"),
      BotCommand(command="scheduled",description="очередь публикаций"),BotCommand(command="games",description="матчи сегодня"),
      BotCommand(command="match",description="разобрать видео"),BotCommand(command="status",description="состояние системы")])
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    for channel,times in settings.schedules.items():
        for i,value in enumerate(times):
            hour,minute=map(int,value.split(":")); scheduler.add_job(generate,"cron",args=[channel],hour=hour,minute=minute,id=f"{channel}_{i}")
    scheduler.add_job(due,"interval",seconds=30,id="publish_due")
    if analytics.ready: scheduler.add_job(analytics.sync,"interval",minutes=settings.analytics_sync_minutes,id="analytics_sync")
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    if shop_bot:
        await shop_bot.delete_webhook(drop_pending_updates=True)
        await asyncio.gather(dp.start_polling(bot),shop_dp.start_polling(shop_bot))
    else: await dp.start_polling(bot)

if __name__=="__main__": asyncio.run(main())
