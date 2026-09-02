import asyncio
import html
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .channels import CHANNELS
from .config import load_settings
from .database import Database
from .editor import Editor
from .history import HistoryImporter
from .gifts_data import GiftsDataDesk
from .analytics import AnalyticsCollector
from .video import VideoFactory

settings=load_settings(); db=Database(settings.database_path,settings.timezone); editor=Editor(settings,db)
videos=VideoFactory(settings,db,editor)
history=HistoryImporter(db)
gifts_data=GiftsDataDesk(settings)
analytics=AnalyticsCollector(settings,db)
bot=Bot(settings.bot_token); router=Router(); dp=Dispatcher(); dp.include_router(router)
logging.basicConfig(level=getattr(logging, __import__("os").getenv("LOG_LEVEL","INFO").upper()))
log=logging.getLogger("content-os")

class ScheduleState(StatesGroup):
    waiting_datetime = State()

def admin(obj): return bool(obj.from_user and obj.from_user.username and obj.from_user.username.lower() in settings.admins)

def keyboard(draft_id):
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="✅ В канал",callback_data=f"publish:{draft_id}"),InlineKeyboardButton(text="⏰ Выбрать время",callback_data=f"schedule:{draft_id}")],
      [InlineKeyboardButton(text="🔥 Жёстче",callback_data=f"harder:{draft_id}"),InlineKeyboardButton(text="🔄 Другой заход",callback_data=f"rewrite:{draft_id}")],
      [InlineKeyboardButton(text="✂️ Короче",callback_data=f"short:{draft_id}"),InlineKeyboardButton(text="🎬 Shorts",callback_data=f"shorts:{draft_id}")],
      [InlineKeyboardButton(text="🗑 Удалить",callback_data=f"delete:{draft_id}")]])

async def review(draft_id):
    draft=db.draft(draft_id); cfg=CHANNELS[draft["channel_key"]]; chat=db.get("admin_chat_id")
    if chat: await bot.send_message(int(chat),f"{cfg['emoji']} <b>{cfg['title']} · {draft['format_key']} · хук {draft['hook_score']}/5</b>\n\n{html.escape(draft['text'])}",
                                    parse_mode=ParseMode.HTML,reply_markup=keyboard(draft_id),disable_web_page_preview=True)

async def generate(channel_key):
    try:
        draft_id=await editor.create(channel_key)
        if settings.auto_publish: await publish(draft_id)
        else: await review(draft_id)
    except Exception: log.exception("Generation failed for %s",channel_key)

async def publish(draft_id):
    draft=db.draft(draft_id); sent=await bot.send_message(settings.channels[draft["channel_key"]],draft["text"])
    db.update(draft_id,status="published",published_at=datetime.now(settings.timezone).isoformat(),published_message_id=sent.message_id)

@router.message(CommandStart())
async def start(message:Message):
    if not admin(message): return await message.answer("Это закрытая редакция.")
    db.set("admin_chat_id",str(message.chat.id)); await message.answer("🧠 <b>Content OS запущена</b>\n\n/generate — новый материал\n/giftpost — пост из рыночных данных\n/sync — обновить историю каналов\n/analytics — эффективность постов\n/status — состояние",parse_mode=ParseMode.HTML)

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
        draft_id=await editor.create_gifts_data_post(facts); await wait.edit_text(f"✅ Рыночный срез собран. Ошибок источников: {len(snapshot['errors'])}")
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

@router.message(Command("generate"))
async def menu(message:Message):
    if not admin(message): return
    await message.answer("Куда бьём?",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
      InlineKeyboardButton(text="⚽ Лига",callback_data="gen:liga"),InlineKeyboardButton(text="🎁 Gifts",callback_data="gen:gifts")]]))

@router.callback_query(F.data.startswith("gen:"))
async def gen_cb(c:CallbackQuery):
    if not admin(c): return
    await c.answer("Редакция ищет сильный заход…"); await generate(c.data.split(":")[1])

@router.callback_query(F.data.startswith("publish:"))
async def pub_cb(c:CallbackQuery):
    if not admin(c): return
    await publish(int(c.data.split(":")[1])); await c.message.edit_reply_markup(reply_markup=None); await c.answer("Опубликовано")

@router.callback_query(F.data.startswith(("harder:","rewrite:","short:")))
async def rewrite_cb(c:CallbackQuery):
    if not admin(c): return
    mode,draft_id=c.data.split(":"); draft_id=int(draft_id); await c.answer("Переписываю…")
    text,score=await editor.rewrite(db.draft(draft_id),mode); db.update(draft_id,text=text,hook_score=score)
    await c.message.edit_text(f"📝 <b>Черновик #{draft_id} · хук {score}/5</b>\n\n{html.escape(text)}",parse_mode=ParseMode.HTML,reply_markup=keyboard(draft_id))

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
    db.update(draft_id,status="scheduled",scheduled_at=when.isoformat()); await c.message.edit_reply_markup(reply_markup=None); await c.answer(f"Поставлено на {when:%d.%m %H:%M}",show_alert=True)

@router.callback_query(F.data.startswith("customat:"))
async def custom_schedule(c:CallbackQuery,state:FSMContext):
    if not admin(c): return
    draft_id=int(c.data.split(":")[1]); await state.set_state(ScheduleState.waiting_datetime); await state.update_data(draft_id=draft_id)
    await c.message.answer("Напиши дату и время по Екатеринбургу:\n<code>03.09 14:35</code>",parse_mode=ParseMode.HTML); await c.answer()

@router.message(ScheduleState.waiting_datetime)
async def custom_schedule_value(message:Message,state:FSMContext):
    if not admin(message): return
    try:
        value=datetime.strptime(message.text.strip(),"%d.%m %H:%M").replace(year=datetime.now(settings.timezone).year,tzinfo=settings.timezone)
        if value<=datetime.now(settings.timezone): raise ValueError
    except (ValueError,AttributeError):
        return await message.answer("Не понял время. Пример: <code>03.09 14:35</code>",parse_mode=ParseMode.HTML)
    data=await state.get_data(); db.update(data["draft_id"],status="scheduled",scheduled_at=value.isoformat()); await state.clear()
    await message.answer(f"⏰ Пост #{data['draft_id']} поставлен на {value:%d.%m в %H:%M}.")

@router.callback_query(F.data.startswith("back:"))
async def back_to_draft(c:CallbackQuery):
    if not admin(c): return
    draft_id=int(c.data.split(":")[1]); await c.message.edit_reply_markup(reply_markup=keyboard(draft_id)); await c.answer()

@router.callback_query(F.data.startswith("delete:"))
async def delete(c:CallbackQuery):
    if not admin(c): return
    db.update(int(c.data.split(":")[1]),status="deleted"); await c.message.edit_reply_markup(reply_markup=None); await c.answer("Удалено")

@router.callback_query(F.data.startswith("shorts:"))
async def create_shorts(c:CallbackQuery):
    if not admin(c): return
    draft_id=int(c.data.split(":")[1]); await c.answer("Собираю хук, озвучку и сцены…")
    try:
        job_id,data,payload,delivered=await videos.create(db.draft(draft_id))
        scenes="\n".join(f"{i+1}. {s['seconds']}с · {s['screen_text']}\n{s['visual']}" for i,s in enumerate(data["scenes"]))
        await c.message.answer(
          f"🎬 <b>Shorts #{job_id} · {html.escape(data['title'])}</b>\n\n"
          f"<b>Хук:</b> {html.escape(data['hook'])}\n\n<b>Озвучка:</b>\n{html.escape(data['voiceover'])}\n\n"
          f"<b>Монтаж:</b>\n{html.escape(scenes)}\n\n<b>CTA:</b> {html.escape(data['cta'])}\n\n"
          f"⚙️ {'Отправлен в MPT' if delivered else 'JSON готов; webhook MPT пока не задан'}",parse_mode=ParseMode.HTML)
        await bot.send_document(c.message.chat.id,BufferedInputFile(payload.encode(),filename=f"shorts-job-{job_id}.json"),caption="Задание для MoneyPrinterTurbo/монтажа")
    except Exception as exc:
        log.exception("Shorts generation failed"); await c.message.answer(f"❌ Shorts не собрался: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)

@router.message(Command("status"))
async def status(message:Message):
    if not admin(message): return
    counts="\n".join(f"@{r['source_channel']} ({r['source_role']}): {r['count']}" for r in db.import_counts()) or "история ещё не загружена"
    await message.answer(f"AI: {'готов' if settings.llm_key else 'нет ключа'}\n⚽ {settings.channels['liga']}\n🎁 {settings.channels['gifts']}\nАвтопубликация: {'да' if settings.auto_publish else 'нет'}\n\n<b>Память:</b>\n{counts}",parse_mode=ParseMode.HTML)

async def due():
    for draft in db.scheduled(datetime.now(settings.timezone).isoformat()):
        try: await publish(draft["id"])
        except Exception: log.exception("Publish failed: %s",draft["id"])

async def main():
    db.init(); scheduler=AsyncIOScheduler(timezone=settings.timezone)
    for channel,times in settings.schedules.items():
        for i,value in enumerate(times):
            hour,minute=map(int,value.split(":")); scheduler.add_job(generate,"cron",args=[channel],hour=hour,minute=minute,id=f"{channel}_{i}")
    scheduler.add_job(due,"interval",seconds=30,id="publish_due")
    if analytics.ready: scheduler.add_job(analytics.sync,"interval",minutes=settings.analytics_sync_minutes,id="analytics_sync")
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True); await dp.start_polling(bot)

if __name__=="__main__": asyncio.run(main())
