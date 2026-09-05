from __future__ import annotations

import html
import json
import os
from collections import Counter
from datetime import date, datetime

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .autopilot_v2 import AutopilotAction, build_autopilot_plan
from .channels import CHANNELS
from .football_challenges import daily_challenge
from .growth.attribution import normalize_event_type
from .growth.recommendations import recommendation_pack
from .growth.analytics_v2 import build_growth_summary
from .editorial_memory import EditorialMemory
from .meme_engine import build_meme
from .planner_v2 import ContentCandidate
from .release_gate import evaluate_release
from .system_health import subsystem_statuses

PLAN_KEY = "v2:today:actions"


def operator_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ TODAY", callback_data="v2:today"), InlineKeyboardButton(text="✚ CREATE", callback_data="v2:create")],
        [InlineKeyboardButton(text="📁 PROJECTS", callback_data="v2:projects"), InlineKeyboardButton(text="📅 CALENDAR", callback_data="panel:scheduled")],
        [InlineKeyboardButton(text="🎬 STUDIO", callback_data="v2:studio"), InlineKeyboardButton(text="📊 GROWTH", callback_data="v2:growth")],
        [InlineKeyboardButton(text="🛒 SALES", callback_data="v2:sales"), InlineKeyboardButton(text="🧠 KNOWLEDGE", callback_data="v2:knowledge")],
        [InlineKeyboardButton(text="⚙️ SYSTEM", callback_data="v2:readiness")],
    ])


def home_nav() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⌂ На главную", callback_data="panel:home")]])


def section_nav(back: str = "panel:home") -> list[list[InlineKeyboardButton]]:
    return [[InlineKeyboardButton(text="‹ Назад", callback_data=back), InlineKeyboardButton(text="⌂ Главная", callback_data="panel:home")]]


def _value(row, key, default=""):
    try: return row.get(key, default) if hasattr(row, "get") else row[key]
    except Exception: return default


def _first_line(value: str, limit: int = 110) -> str:
    line=next((part.strip(" •—–\t") for part in str(value or "").splitlines() if part.strip()),"")
    return line[:limit].rstrip()


def _recent_candidates(db) -> list[ContentCandidate]:
    """Turn observed radar material into ideas, never unsupported market facts."""
    result=[]
    for project in ("gifts","liga"):
        try: rows=list(db.radar_posts(project,10))
        except Exception: rows=[]
        for index,row in enumerate(rows[:6]):
            topic=_first_line(_value(row,"text"))
            if not topic: continue
            result.append(ContentCandidate(
                project=project,kind=("shorts","post","meme")[index%3],topic=topic,
                source=str(_value(row,"source_channel","telegram-radar")),freshness=max(.62,.94-index*.05),
                relevance=.82,novelty=max(.60,.86-index*.04),evidence=.58 if project=="gifts" else .68,
                sales_value=.55 if project=="gifts" else .30,urgency=.65 if index<2 else .35,fact_sensitive=project=="gifts"))
        for index,topic in enumerate((CHANNELS[project].get("topics") or [])[:5]):
            kinds=("post","meme","challenge" if project=="liga" else "shorts")
            result.append(ContentCandidate(project=project,kind=kinds[index%3],topic=str(topic),source="content-dna",
                freshness=.55,relevance=.76,novelty=.72,evidence=.78,sales_value=.28,urgency=.20))
    return result


def _serialize_actions(actions: tuple[AutopilotAction,...]) -> str:
    return json.dumps([{"project":a.project,"kind":a.kind,"title":a.title,
        "payload":a.payload if isinstance(a.payload,dict) else {},"requires_review":True} for a in actions],ensure_ascii=False)


def _load_actions(db) -> list[dict]:
    try: return list(json.loads(db.get(PLAN_KEY) or "[]"))
    except (TypeError,ValueError,json.JSONDecodeError): return []


def _growth_rows(db) -> list[dict]:
    try: metrics=list(db.analytics_summary(500))
    except Exception: metrics=[]
    memories={project:{str(item.get("draft_id")):item.get("fingerprint") or {} for item in EditorialMemory(db)._json(f"v2:fingerprints:{project}",[])} for project in ("gifts","liga")}
    rows=[]
    for metric in metrics:
        project=str(_value(metric,"channel_key")); draft_id=str(_value(metric,"id")); fp=memories.get(project,{}).get(draft_id,{})
        rows.append({"project":project,"hook_type":fp.get("hook_type","unknown"),"format":fp.get("format_key",_value(metric,"format_key","unknown")),
            "visual_type":fp.get("visual_type","unknown"),"publish_hour":"unknown","offer":fp.get("cta_type","none"),
            "engagement_rate":float(_value(metric,"engagement",0) or 0),"conversion_rate":0.0})
    return rows


def _plan_keyboard(actions: tuple[AutopilotAction,...]) -> InlineKeyboardMarkup:
    icons={"gifts":"🎁","liga":"⚽","shorts":"▶","meme":"◉","post":"✦","challenge":"◎"}; rows=[]
    for index,action in enumerate(actions):
        rows.append([InlineKeyboardButton(text=f"{icons.get(action.project,'✦')}{icons.get(action.kind,'✦')} Создать · {action.title[:35]}",callback_data=f"v2:make:{index}")])
    if actions: rows.append([InlineKeyboardButton(text="⚡ Создать весь план",callback_data="v2:makeall")])
    rows.append([InlineKeyboardButton(text="↻ Пересобрать план",callback_data="v2:today:refresh")]); rows.extend(section_nav())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _today_text(plan) -> str:
    lines=[f"<b>CONTENT OS  /  {datetime.now():%d.%m}</b>","<i>Редакционный пульт на сегодня</i>"]
    for project,name in (("gifts","GIFTS INTELLIGENCE"),("liga","LIGAPROGRESS")):
        items=[item for item in plan.editorial.items if item.project==project]; lines.append(f"\n<b>{name}</b>")
        if not items: lines.append("<i>Нет достаточно сильных тем — слабый контент не производим</i>")
        for item in items:
            kind={"post":"POST","shorts":"SHORTS","meme":"MEME","challenge":"CHALLENGE"}.get(item.kind,item.kind.upper())
            lines.append(f"\n<code>{kind:9}</code> {html.escape(item.topic[:90])}\n<i>{html.escape(item.reason)} · {item.score}/100</i>")
    lines.append("\n<i>Ничего не публикуется автоматически: каждый материал проходит Director и твоё подтверждение</i>")
    return "\n".join(lines)


async def _create_action(legacy,action:dict) -> int:
    project=str(action.get("project") or "liga").lower(); project="liga" if project=="ligaprogress" else project
    kind=str(action.get("kind") or "post").lower(); title=str(action.get("title") or "").strip()
    payload=action.get("payload") if isinstance(action.get("payload"),dict) else {}
    if kind in {"challenge","football_challenge"} and project=="liga":
        challenge=daily_challenge("community","all",date.today())
        brief=(f"Футбольный челлендж дня: {challenge.title}. {challenge.task} "
               f"Критерий: {challenge.success_metric}. Подтверждение: {challenge.proof}. "
               "Сделай пост, который хочется выполнить и отправить другу.")
        return await legacy.editor.create_from_brief("liga","challenge",brief,challenge.title)
    if kind=="meme":
        concept=build_meme(project,title)
        brief=f"Сделай короткий мем-пост. Ситуация: {concept.situation}. Setup: {concept.setup}. Punchline: {concept.punchline}. Не добавляй неподтверждённых цифр. Тон живой, не нейросетевой."
        return await legacy.editor.create_from_brief(project,"meme",brief,title)
    reason=str(payload.get("reason") or "выбран редакционным планом"); source=str(payload.get("source") or "")
    format_key="short_story" if kind=="shorts" else "intelligence" if project=="gifts" else "story"
    brief=(f"Тема: {title}. Причина выбора: {reason}. Источник темы: {source or 'Content DNA'}. "
           "Источник — только сигнал темы, не доказательство фактов. Без fact pack не утверждай цены, сделки, спрос, результаты или статистику. "
           "Найди один сильный конфликт, узнаваемую деталь и практический вывод.")
    return await legacy.editor.create_from_brief(project,format_key,brief,title)


def install(legacy):
    router=Router(name="content-os-cockpit-v2"); legacy.main_keyboard=operator_keyboard

    @router.callback_query(F.data.in_({"v2:today","v2:today:refresh"}))
    async def today(c:CallbackQuery):
        if not legacy.admin(c): return
        await c.answer("Собираю сильнейший план…"); candidates=_recent_candidates(legacy.db); recent={}
        for project in ("gifts","liga"):
            try: recent[project]=[str(_value(row,"format_key")) for row in legacy.db.recent_drafts(project,8)]
            except Exception: recent[project]=[]
        plan=build_autopilot_plan(candidates,recent_kinds=recent,day=date.today(),per_project=3)
        legacy.db.set(PLAN_KEY,_serialize_actions(plan.actions))
        await c.message.edit_text(_today_text(plan),parse_mode=ParseMode.HTML,reply_markup=_plan_keyboard(plan.actions))

    @router.callback_query(F.data.startswith("v2:make:"))
    async def make_one(c:CallbackQuery):
        if not legacy.admin(c): return
        raw=c.data.rsplit(":",1)[-1]; actions=_load_actions(legacy.db)
        if not raw.isdigit() or int(raw)>=len(actions): return await c.answer("План устарел — пересобери TODAY",show_alert=True)
        await c.answer("Запускаю Content Factory…"); wait=await c.message.answer("✦ <b>CONTENT FACTORY</b>\n\nСейчас: сценарий и фактические границы",parse_mode=ParseMode.HTML)
        try: draft_id=await _create_action(legacy,actions[int(raw)])
        except Exception as exc: return await wait.edit_text(f"❌ Factory остановлен: {html.escape(str(exc)[:320])}",parse_mode=ParseMode.HTML)
        await wait.edit_text("✓ Черновик создан\n✓ Fact safety применён\n→ Creative Director",parse_mode=ParseMode.HTML); await legacy.review(draft_id)

    @router.callback_query(F.data=="v2:makeall")
    async def make_all(c:CallbackQuery):
        if not legacy.admin(c): return
        actions=_load_actions(legacy.db)
        if not actions: return await c.answer("Сначала собери план",show_alert=True)
        await c.answer("Запускаю фабрику…"); status=await c.message.answer(f"⚡ <b>CONTENT FACTORY · 0/{len(actions)}</b>",parse_mode=ParseMode.HTML); made=[]; errors=[]
        for index,action in enumerate(actions,1):
            try: made.append(await _create_action(legacy,action))
            except Exception as exc: errors.append(f"{action.get('title','тема')[:35]}: {str(exc)[:80]}")
            await status.edit_text(f"⚡ <b>CONTENT FACTORY · {index}/{len(actions)}</b>\n\nГотово: {len(made)} · остановлено: {len(errors)}",parse_mode=ParseMode.HTML)
        for draft_id in made: await legacy.review(draft_id)
        summary=f"✓ Передано Director: {len(made)}\n✕ Остановлено: {len(errors)}"
        if errors: summary+="\n\n"+"\n".join(f"• {html.escape(x)}" for x in errors[:5])
        await status.edit_text(f"<b>CONTENT FACTORY ЗАВЕРШЕНА</b>\n\n{summary}",parse_mode=ParseMode.HTML,reply_markup=home_nav())

    @router.callback_query(F.data=="v2:create")
    async def create_hub(c:CallbackQuery):
        if not legacy.admin(c): return
        rows=[[InlineKeyboardButton(text="🎁 Gifts · пост",callback_data="gen:gifts"),InlineKeyboardButton(text="⚽ Liga · пост",callback_data="gen:liga")],
              [InlineKeyboardButton(text="◎ Рыночный срез",callback_data="panel:gifts"),InlineKeyboardButton(text="◉ Матч",callback_data="panel:games")],
              [InlineKeyboardButton(text="◆ Из базы знаний",callback_data="v2:knowledge"),InlineKeyboardButton(text="⚡ План дня",callback_data="v2:today")],*section_nav()]
        await c.answer(); await c.message.edit_text("<b>＋ CREATE</b>\n\nВыбери результат. После создания материал автоматически пройдёт Director и получит визуальные варианты.",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    @router.callback_query(F.data=="v2:projects")
    async def projects(c:CallbackQuery):
        if not legacy.admin(c): return
        rows=[[InlineKeyboardButton(text="🎁 Gifts Intelligence",callback_data="v2:project:gifts")],[InlineKeyboardButton(text="⚽ LigaProgress",callback_data="v2:project:liga")],
              [InlineKeyboardButton(text="✦ AI Content Lab",callback_data="v2:project:services")],*section_nav()]
        await c.answer(); await c.message.edit_text("<b>◫ PROJECTS</b>\n\nТри продукта. Одна память, одна фабрика и одна аналитика — но разные Content DNA, офферы и цели.",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    @router.callback_query(F.data.startswith("v2:project:"))
    async def project(c:CallbackQuery):
        if not legacy.admin(c): return
        key=c.data.rsplit(":",1)[-1]; configs={
          "gifts":("GIFTS INTELLIGENCE","Рынок · психология · безопасность · мемы · подписка",[("◎ Market Desk","panel:gifts"),("＋ Новый пост","gen:gifts"),("◆ Knowledge","coursemake:gifts")]),
          "liga":("LIGAPROGRESS","Истории · обучение · матчи · challenges · развитие игрока",[("◎ Challenge дня","v2:challenge"),("＋ Новый пост","gen:liga"),("◉ Матчи","panel:games"),("◆ Football Lab","panel:football")]),
          "services":("AI CONTENT LAB","Shorts Pack · Telegram Growth Pack · Content OS Setup",[("₽ Sales Engine","v2:sales"),("↗ Growth","v2:growth"),("◆ Knowledge","v2:knowledge")])}
        if key not in configs: return await c.answer("Проект не найден",show_alert=True)
        title,subtitle,actions=configs[key]; rows=[]
        for index in range(0,len(actions),2): rows.append([InlineKeyboardButton(text=x[0],callback_data=x[1]) for x in actions[index:index+2]])
        rows.extend(section_nav("v2:projects")); await c.answer(); await c.message.edit_text(f"<b>{title}</b>\n<i>{subtitle}</i>\n\nТолько действия этого продукта — без технической свалки остальных модулей.",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    @router.callback_query(F.data=="v2:studio")
    async def studio(c:CallbackQuery):
        if not legacy.admin(c): return
        rows=[[InlineKeyboardButton(text="＋ Создать пост для Shorts",callback_data="v2:create")],[InlineKeyboardButton(text="🎙 Проверить worker",callback_data="panel:status")],*section_nav()]
        await c.answer(); await c.message.edit_text("<b>▶ SHORTS STUDIO</b>\n\n01  Сценарий\n02  Подтверждение\n03  Голос\n04  Сцены\n05  Субтитры\n06  Рендер\n\nПосле ролика можно отдельно заменить голос, кадры или субтитры. Своя MP3/голосовое поддерживаются.",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    @router.callback_query(F.data=="v2:knowledge")
    async def knowledge(c:CallbackQuery):
        if not legacy.admin(c): return
        try: rows=list(legacy.db.course_snippets(500))
        except Exception: rows=[]
        areas=Counter()
        for row in rows:
            text=str(_value(row,"text")).lower()
            for key,terms in {"hooks":("хук","вниман"),"sales":("продаж","оффер"),"retention":("удержан","досмотр"),"shorts":("shorts","ролик","видео"),"funnels":("ворон","лид")}.items():
                if any(term in text for term in terms): areas[key]+=1
        area_text=" · ".join(f"{key} {count}" for key,count in areas.most_common()) or "таксономия появится после загрузки"
        buttons=[[InlineKeyboardButton(text="＋ Добавить материалы",callback_data="panel:coursefile"),InlineKeyboardButton(text="↻ Синхронизировать",callback_data="panel:coursesync")],
                 [InlineKeyboardButton(text="🎁 Применить к Gifts",callback_data="coursemake:gifts"),InlineKeyboardButton(text="⚽ Применить к Liga",callback_data="coursemake:liga")],
                 [InlineKeyboardButton(text="▦ Что загружено",callback_data="panel:coursestats")],*section_nav()]
        await c.answer(); await c.message.edit_text(f"<b>◆ KNOWLEDGE ENGINE</b>\n\nФрагментов: <b>{len(rows)}</b>\n{html.escape(area_text)}\n\nКурсы дают принципы, чеклисты и frameworks. Они не становятся рыночными фактами и не копируются в публикации.",parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    @router.callback_query(F.data=="v2:sales")
    async def sales(c:CallbackQuery):
        if not legacy.admin(c): return
        try: orders=list(legacy.db.service_orders("new",50)); events=list(legacy.db.funnel_events(5000))
        except Exception: orders=[]; events=[]
        types=Counter(normalize_event_type(str(_value(x,"event_type"))) for x in events)
        text=("<b>₽ SALES ENGINE</b>\n\n"+f"Новые заявки  <b>{len(orders)}</b>\nПереходы  <b>{types['visit']}</b>\nЛиды  <b>{types['lead']}</b>\nПродажи  <b>{types['sale']}</b>\n\n"
              "<b>Линейка</b>\nFootball · Episode Review / Player Development\nAI Lab · Shorts / Telegram Growth / Content OS Setup\nGifts · переход в Gifts Intelligence")
        buttons=[[InlineKeyboardButton(text="▦ Новые заявки",callback_data="panel:orders"),InlineKeyboardButton(text="↗ Воронка",callback_data="panel:funnel")],[InlineKeyboardButton(text="Открыть магазин",callback_data="panel:shop")],*section_nav()]
        await c.answer(); await c.message.edit_text(text,parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    @router.callback_query(F.data=="v2:growth")
    async def growth(c:CallbackQuery):
        if not legacy.admin(c): return
        try: events=list(legacy.db.funnel_events(5000)); metrics=list(legacy.db.analytics_summary(100))
        except Exception: events=[]; metrics=[]
        counts=Counter(normalize_event_type(str(_value(event,"event_type"))) for event in events); sources=Counter(str(_value(event,"source")) for event in events if _value(event,"source"))
        top="\n".join(f"{index:02}  {html.escape(source[:45])}  · {count}" for index,(source,count) in enumerate(sources.most_common(4),1)) or "<i>Недостаточно событий</i>"
        growth_rows=_growth_rows(legacy.db); recs=[]
        for project in ("gifts","liga"): recs.extend(recommendation_pack(growth_rows,project))
        recommendation_text="\n".join(f"• {r.project}: проверить {r.dimension} = {r.value} <i>({r.confidence})</i>" for r in recs[:5]) or "<i>Сначала нужно минимум 5 сопоставимых материалов — не переобучаемся на случайной удаче</i>"
        text=("<b>↗ GROWTH</b>\n<i>От внимания до денег</i>\n\n"+f"VIEWS DATA  <b>{len(metrics)}</b> постов\nVISITS  <b>{counts['visit']}</b>\nLEADS  <b>{counts['lead']}</b>\nORDERS  <b>{counts['order']}</b>\nSALES  <b>{counts['sale']}</b>\n\n"+f"<b>Источники</b>\n{top}\n\n<b>Следующие эксперименты</b>\n{recommendation_text}\n\n<i>Меняем одну переменную за раз; корреляция не выдаётся за причину</i>")
        buttons=[[InlineKeyboardButton(text="↻ Обновить метрики",callback_data="panel:postmetrics"),InlineKeyboardButton(text="◎ Воронка",callback_data="panel:funnel")],
                 [InlineKeyboardButton(text="◷ Окна 1 / 6 / 24 / 48ч",callback_data="v2:growth:windows")],
                 [InlineKeyboardButton(text="A/B · Gifts",callback_data="v2:experiment:gifts"),InlineKeyboardButton(text="A/B · Liga",callback_data="v2:experiment:liga")],*section_nav()]
        await c.answer(); await c.message.edit_text(text,parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    @router.callback_query(F.data.startswith("v2:experiment:"))
    async def experiment(c:CallbackQuery):
        if not legacy.admin(c): return
        project=c.data.rsplit(":",1)[-1]; recs=recommendation_pack(_growth_rows(legacy.db),project)
        if not recs: return await c.answer("Пока мало данных: нужно минимум 5 сопоставимых материалов",show_alert=True)
        rec=recs[0]; await c.answer("Готовлю контролируемый тест…")
        brief=(f"Контролируемый редакционный эксперимент. Измени только одну переменную: {rec.dimension}={rec.value}. "
               f"Причина: {rec.reason} Остальные особенности обычного материала сохрани. Не обещай рост результата и не придумывай факты.")
        try: draft_id=await legacy.editor.create_from_brief(project,"experiment",brief,f"A/B · {rec.dimension}")
        except Exception as exc: return await c.message.answer(f"❌ Эксперимент не создан: {html.escape(str(exc)[:300])}",parse_mode=ParseMode.HTML)
        await legacy.review(draft_id)

    @router.callback_query(F.data=="v2:growth:windows")
    async def growth_windows(c:CallbackQuery):
        if not legacy.admin(c): return
        drafts=[]
        for project in ("gifts","liga"):
            try: drafts.extend([row for row in legacy.db.recent_drafts(project,20) if _value(row,"status")=="published" and _value(row,"published_at")])
            except Exception: continue
        drafts=sorted(drafts,key=lambda row:str(_value(row,"published_at")),reverse=True)[:8]; blocks=[]
        for draft in drafts:
            try: summary=build_growth_summary(_value(draft,"id"),_value(draft,"published_at"),legacy.db.metrics_for_draft(_value(draft,"id"),100))
            except Exception: continue
            windows="  ".join(f"{hour}ч <b>{snapshot.views}</b>" for hour,snapshot in summary.windows.items()) or "замеры ещё не созрели"
            blocks.append(f"<b>#{_value(draft,'id')} · {html.escape(str(_value(draft,'format_key')))}</b>\n{windows}")
        text="<b>◷ PERFORMANCE WINDOWS</b>\n<i>Просмотры в одинаковом возрасте публикаций</i>\n\n"+("\n\n".join(blocks) if blocks else "Пока нет опубликованных постов с подходящими снимками")
        await c.answer(); await c.message.edit_text(text,parse_mode=ParseMode.HTML,reply_markup=InlineKeyboardMarkup(inline_keyboard=section_nav("v2:growth")))

    @router.callback_query(F.data=="v2:readiness")
    async def readiness(c:CallbackQuery):
        if not legacy.admin(c): return
        gate=evaluate_release(os.environ,require_shorts=True); rows=[]
        for item in subsystem_statuses(os.environ):
            icon="●" if item.ready else "○"; detail=item.warning or ("нужно: "+", ".join(item.missing) if item.missing else "готов")
            rows.append(f"{icon} <b>{html.escape(item.title)}</b>  <i>{html.escape(detail)}</i>")
        warnings="\n".join(f"• {html.escape(item)}" for item in gate.warnings) or "нет"
        text=f"<b>⚙ SYSTEM  /  {'READY' if gate.ready else 'SETUP'}</b>\n\n"+"\n".join(rows)+f"\n\n<b>Предупреждения</b>\n{warnings}\n\n<i>Значения секретов никогда не показываются</i>"
        await c.answer(); await c.message.edit_text(text,parse_mode=ParseMode.HTML,reply_markup=home_nav())

    legacy.dp.include_router(router); return router
