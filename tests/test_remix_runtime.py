import asyncio
import html
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.session.base import BaseSession
from aiogram.types import Message, Update, InlineKeyboardMarkup

from content_os.database import Database
from content_os.draft_navigation import back_to_draft
from content_os.fact_layer import FactPack, FactStore
from content_os.remix import RemixService
from content_os.remix_runtime import install_remix, bundle_keyboard
from content_os.remix_store import RemixStore, load_poll
from content_os.shorts.orchestrator import ShortsStudio

SOURCE = "Игрок дважды не посмотрел через плечо перед приёмом мяча и потерял возможность продолжить атаку."


class Session(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.fail_preview = False

    async def close(self): pass

    async def stream_content(self, *args, **kwargs):
        if False: yield b""

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if method.__api_method__ == "answerCallbackQuery": return True
        if method.__api_method__ == "sendMessage":
            if self.fail_preview and "Большой пост</b>" in method.text:
                self.fail_preview = False
                raise RuntimeError("temporary Telegram failure")
            return Message(message_id=len(self.calls), date=datetime.now(timezone.utc), chat={"id":1,"type":"private"}, text=method.text)
        raise AssertionError(f"Unexpected network action: {method.__api_method__}")


def setup(tmp_path):
    db = Database(str(tmp_path / "remix.db"), timezone.utc)
    db.init()
    source_id = db.save_draft("liga", "story", SOURCE, 4)
    session = Session()
    bot = Bot("123456:TEST_TOKEN", session=session)
    legacy = SimpleNamespace(db=db, dp=Dispatcher(), admin=lambda c: True,
        keyboard=lambda n: InlineKeyboardMarkup(inline_keyboard=[]),
        editor=SimpleNamespace(llm=AsyncMock(return_value="broken json")), review=AsyncMock(),
        render=lambda ch, text: html.escape(text))
    studio = ShortsStudio(SimpleNamespace(mpt_base_url="",mpt_api_key="",mpt_timeout_minutes=10), legacy.editor, db)
    install_remix(legacy, studio)
    nav = Router()
    @nav.callback_query(F.data.startswith("back:"))
    async def back(c, state): await back_to_draft(legacy, c, state)
    legacy.dp.include_router(nav)
    return legacy, studio, bot, session, source_id


async def click(legacy, bot, data, n=1):
    update = Update.model_validate({"update_id":n,"callback_query":{"id":str(n),"from":{"id":1,"is_bot":False,"first_name":"Admin"},"chat_instance":"1","data":data,"message":{"message_id":1,"date":0,"chat":{"id":1,"type":"private"},"text":"menu"}}})
    await legacy.dp.feed_update(bot, update)


def bundle_id_from(session):
    for call in session.calls:
        markup = getattr(call, "reply_markup", None)
        if markup:
            for row in markup.inline_keyboard:
                for button in row:
                    if (button.callback_data or "").startswith("remixv2:save:"):
                        return button.callback_data.split(":")[2]
    raise AssertionError("No Remix controls sent")


def test_dispatcher_remix_preserves_bundles_and_deduplicates_saves(tmp_path):
    legacy, studio, bot, session, source_id = setup(tmp_path)
    async def run():
        await click(legacy, bot, f"remixv2:start:{source_id}")
        first = bundle_id_from(session)
        session.calls.clear()
        await click(legacy, bot, f"remixv2:start:{source_id}")
        second = bundle_id_from(session)
        assert first != second
        assert RemixStore(legacy.db).load(first)
        await asyncio.gather(click(legacy, bot, f"remixv2:save:{first}:long", 3), click(legacy, bot, f"remixv2:save:{first}:long", 4))
        assert len(legacy.db.recent_drafts("liga")) == 2
        assert RemixStore(legacy.db).result(first, "long")
    asyncio.run(run())


def test_shorts_opens_review_without_llm_or_render_and_survives_restart(tmp_path):
    legacy, studio, bot, session, source_id = setup(tmp_path)
    store = RemixStore(legacy.db)
    bundle = RemixService.fallback("liga", SOURCE)
    bid = store.create(legacy.db.draft(source_id), bundle)
    async def run():
        await click(legacy, bot, f"remixv2:save:{bid}:shorts")
        job_id = store.result(bid,"shorts")
        assert job_id
        assert studio.sessions.load(job_id).voiceover == bundle.shorts_script
        assert not studio.sessions.load(job_id).approved
        # New router/store emulates a restarted process using the same database.
        legacy.dp = Dispatcher()
        install_remix(legacy, studio)
        await click(legacy, bot, f"remixv2:save:{bid}:shorts", 2)
        with legacy.db.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM video_jobs").fetchone()[0] == 1
        assert any("shortsv2:" in str(getattr(c,"reply_markup", "")) for c in session.calls)
        legacy.editor.llm.assert_not_called()
        legacy.review.assert_not_called()
    asyncio.run(run())


def test_poll_sales_and_fact_handoff(tmp_path):
    legacy, studio, bot, session, source_id = setup(tmp_path)
    store = RemixStore(legacy.db)
    bundle = RemixService.fallback("liga", SOURCE)
    bid = store.create(legacy.db.draft(source_id), bundle)
    pack = FactPack.create("Подтверждённые данные", "source")
    FactStore(legacy.db).save(source_id, pack)
    async def run():
        for kind in ("poll", "sales", "saleslong", "salesshort", "meme", "short"):
            await click(legacy, bot, f"remixv2:save:{bid}:{kind}")
            draft_id = store.result(bid,kind)
            assert draft_id
            assert FactStore(legacy.db).load(draft_id) == pack
        poll = load_poll(legacy.db,store.result(bid,"poll"))
        assert poll["options"] == list(bundle.poll_options)
        assert bundle.sales_bridge in legacy.db.draft(store.result(bid,"saleslong"))["text"]
        assert all(len(b.callback_data.encode()) <= 64 for row in bundle_keyboard(bid, source_id).inline_keyboard for b in row)
    asyncio.run(run())


def test_preview_failure_keeps_bundle_and_recovery_button(tmp_path):
    legacy, studio, bot, session, source_id = setup(tmp_path)
    session.fail_preview = True
    async def run():
        await click(legacy, bot, f"remixv2:start:{source_id}")
        bid = bundle_id_from(session)
        assert RemixStore(legacy.db).load(bid)
        assert any(f"remixv2:open:{bid}" in str(getattr(c,"reply_markup", "")) for c in session.calls)
        calls = legacy.editor.llm.call_count
        await click(legacy, bot, f"remixv2:open:{bid}")
        assert legacy.editor.llm.call_count == calls
    asyncio.run(run())


def test_deleted_source_old_callback_and_back_navigation(tmp_path):
    legacy, studio, bot, session, source_id = setup(tmp_path)
    async def run():
        await click(legacy, bot, f"back:{source_id}")
        assert any(SOURCE in (getattr(c,"text", "") or "") for c in session.calls)
        legacy.review.assert_not_called()
        legacy.editor.llm.assert_not_called()
        await click(legacy, bot, f"remixv2:save:{source_id}:long")
        assert any("Старый набор" in (getattr(c,"text", "") or "") for c in session.calls)
        legacy.db.update(source_id,status="deleted")
        await click(legacy, bot, f"back:{source_id}")
        assert "удалён" in session.calls[-1].text
    asyncio.run(run())


def test_long_escaped_preview_and_transport_error_retry(tmp_path):
    legacy, studio, bot, session, source_id = setup(tmp_path)
    bundle = RemixService.fallback("liga", SOURCE)
    from dataclasses import replace
    bid = RemixStore(legacy.db).create(legacy.db.draft(source_id),replace(bundle,telegram_long="<&>💎"*1600))
    async def run():
        await click(legacy,bot,f"remixv2:open:{bid}")
        for call in session.calls:
            if call.__api_method__ == "sendMessage":
                assert len(call.text.encode("utf-16-le"))//2 < 4096
                # Every piece is independently parseable Telegram HTML.
                from telethon.extensions.html import parse
                parse(call.text)
        legacy.editor.llm.side_effect = TimeoutError("LLM timeout")
        await click(legacy,bot,f"remixv2:start:{source_id}")
        assert any("Повторить Remix" in str(getattr(c,"reply_markup", "")) for c in session.calls)
    asyncio.run(run())


def test_saved_draft_recovers_if_result_mapping_write_failed(tmp_path):
    legacy, studio, bot, session, source_id=setup(tmp_path)
    store=RemixStore(legacy.db)
    bid=store.create(legacy.db.draft(source_id),RemixService.fallback("liga",SOURCE))
    existing=legacy.db.save_draft("liga","remix_long",SOURCE,4,"Remix","",f"remix:{bid}:long")
    asyncio.run(click(legacy,bot,f"remixv2:save:{bid}:long"))
    assert store.result(bid,"long") == existing
    assert len(legacy.db.recent_drafts("liga")) == 2
