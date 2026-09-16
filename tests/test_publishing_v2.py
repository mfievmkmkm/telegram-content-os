import asyncio
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from content_os.editorial_memory import EditorialMemory
from content_os.formatting import decorate_post, telegram_html
from content_os.publishing_v2 import PublishingService


class Row(dict):
    pass


class DB:
    def __init__(self):
        self.settings = {}
        self.row = Row(
            id=8,
            channel_key="gifts",
            format_key="разбор_ошибки",
            text="Смотри не только на картинку\n\nКонтекст важнее одной цифры",
            source_url="",
        )
        self.updated = {}
    def get(self, key): return self.settings.get(key)
    def set(self, key, value): self.settings[key] = value
    def draft(self, draft_id): return self.row if int(draft_id) == 8 else None
    def update(self, draft_id, **fields): self.updated.update(fields)


class Bot:
    def __init__(self, username="shopbot"): self.photos = []; self.messages = []; self.username = username
    async def send_photo(self, channel, photo, **kwargs):
        self.photos.append((channel, kwargs)); return SimpleNamespace(message_id=91)
    async def send_message(self, channel, text, **kwargs):
        self.messages.append((channel, text, kwargs)); return SimpleNamespace(message_id=92)
    async def get_me(self): return SimpleNamespace(username=self.username)


class Premium:
    def __init__(self, ready=False, error=None): self.ready = ready; self.sent = []; self.error = error
    async def send(self, channel, text, image=None):
        self.sent.append((channel, text, image))
        if self.error: raise self.error
        return SimpleNamespace(id=93)


async def no_image(url): return None


def make_legacy(db, bot, shop_bot=None, shop_cta_every=0, premium=None):
    return SimpleNamespace(
        db=db,
        bot=bot,
        shop_bot=shop_bot,
        premium_publisher=premium or Premium(),
        settings=SimpleNamespace(
            channels={"gifts": "@gifts", "liga": "@liga"},
            timezone=ZoneInfo("UTC"),
            shop_cta_every=shop_cta_every,
        ),
        render=lambda channel, text: telegram_html(
            decorate_post(text,channel),
            {"💎":"101","🧠":"102","⚡":"103","🎯":"104"},
        ),
        use_gift_card=lambda draft_id: True,
        use_liga_card=lambda draft_id: True,
        discover_image=no_image,
    )


def test_publish_refuses_bot_fallback_before_any_side_effect():
    db = DB(); memory = EditorialMemory(db); memory.select_variant(8, 1, db.row["text"])
    bot = Bot()
    service = PublishingService(make_legacy(db, bot), memory)
    with pytest.raises(RuntimeError,match="Premium Publish обязателен"):
        asyncio.run(service.publish(8))
    assert bot.photos == [] and bot.messages == []
    assert db.updated == {}


def test_premium_publish_receives_card_and_caption_together():
    db = DB(); memory = EditorialMemory(db); memory.select_variant(8, 1, db.row["text"])
    bot = Bot(); premium = Premium(ready=True)
    service = PublishingService(make_legacy(db, bot, premium=premium), memory)
    mode, error = asyncio.run(service.publish(8))
    assert mode == "premium"
    assert error is None
    assert premium.sent[0][2]
    assert bot.photos == [] and bot.messages == []
    assert db.updated["published_message_id"] == 93


def test_oversize_card_is_rejected_before_partial_publish():
    db = DB(); db.row["text"] = "Слишком длинно. " * 100
    memory = EditorialMemory(db); memory.select_variant(8, 1, db.row["text"])
    bot = Bot(); premium = Premium(ready=True); service = PublishingService(make_legacy(db, bot, premium=premium), memory)
    with pytest.raises(ValueError, match="Подогнать под карточку"):
        asyncio.run(service.publish(8))
    assert bot.photos == [] and bot.messages == [] and premium.sent == []
    assert db.updated == {}


def test_premium_failure_never_falls_back_to_bot_api():
    db = DB(); memory = EditorialMemory(db); bot = Bot()
    premium = Premium(ready=True,error=ConnectionError("session expired"))
    service = PublishingService(make_legacy(db,bot,premium=premium),memory)
    with pytest.raises(RuntimeError,match="пост не опубликован"):
        asyncio.run(service.publish(8))
    assert bot.photos == [] and bot.messages == []
    assert db.updated == {}


def test_publish_cta_uses_campaign_payload_when_shop_bot_exists():
    db = DB(); memory = EditorialMemory(db); bot = Bot("editorbot"); shop = Bot("shopbot"); premium=Premium(ready=True)
    service = PublishingService(make_legacy(db, bot, shop_bot=shop, shop_cta_every=4,premium=premium), memory)
    markup, link = asyncio.run(service._sales_cta(db.row))
    assert markup is None
    url = link
    assert "https://t.me/shopbot?start=c_g_8_p_gifts-access_organic" in url
    assert "service_gifts" not in url


def test_poll_is_structured_and_does_not_publish_a_text_post():
    from content_os.remix_store import save_poll
    from unittest.mock import AsyncMock
    db = DB(); db.row.update(format_key="remix_poll",source_title="Remix #1",status="review")
    save_poll(db,8,"Что проверяешь первым?",["Контекст","Детали"])
    premium = Premium(ready=True)
    premium.send_poll = AsyncMock(return_value=SimpleNamespace(id=94))
    legacy = make_legacy(db,Bot(),premium=premium)
    service = PublishingService(legacy,EditorialMemory(db))
    assert asyncio.run(service.publish(8)) == ("premium",None)
    assert premium.sent == []
    assert premium.send_poll.call_args.args[2] == ["Контекст","Детали"]
    assert db.updated["published_message_id"] == 94
    db.row.update(db.updated)
    with pytest.raises(ValueError,match="уже опубликован"):
        asyncio.run(service.publish(8))
    assert premium.send_poll.call_count == 1


def test_missing_poll_metadata_blocks_publication():
    db = DB(); db.row.update(format_key="remix_poll")
    premium=Premium(ready=True)
    service=PublishingService(make_legacy(db,Bot(),premium=premium),EditorialMemory(db))
    with pytest.raises(ValueError,match="Опрос не найден"):
        asyncio.run(service.publish(8))
    assert premium.sent == [] and db.updated == {}


def test_caption_budget_counts_rendered_entities_and_utf16():
    from content_os.publishing_v2 import caption_length
    assert caption_length('<b>A &amp; B</b>') == 5
    assert caption_length('<tg-emoji emoji-id="123">💎</tg-emoji>') == 2


def test_fit_caption_includes_cta_and_requires_another_publish_action():
    from unittest.mock import AsyncMock
    from content_os.publishing_v2 import caption_length
    db = DB(); original = "Исходный разбор. " * 110; db.row["text"] = original; db.row["source_title"] = "Исходный разбор"
    db.style_examples = lambda *args,**kwargs: []
    premium=Premium(ready=True)
    legacy=make_legacy(db,Bot(),shop_bot=Bot(),shop_cta_every=4,premium=premium)
    compact=("Ты проверил картинку. А смысл?\n\n"
             "Сначала посмотри, что именно ты выбираешь, и только потом сравнивай варианты. "
             "Одна красивая обложка не объясняет ценность предмета и не заменяет проверку деталей. "
             "Если сомневаешься, собери факты, проверь контекст и не спеши с выводом. Сохрани этот разбор")
    legacy.editor=SimpleNamespace(llm=AsyncMock(side_effect=[original,compact]))
    service=PublishingService(legacy,EditorialMemory(db))
    candidate,rendered=asyncio.run(service.fit_caption(8))
    assert caption_length(rendered) <= 1000
    assert "https://t.me/shopbot" in rendered
    assert db.updated["text"] == candidate["text"]
    assert db.updated["status"] == "review" and db.updated["scheduled_at"] is None
    assert premium.sent == []
    assert db.get("v2:caption_original:8") == original


def test_failed_fit_preserves_original_text():
    from unittest.mock import AsyncMock
    db=DB(); original="Исходный разбор. "*110; db.row["text"]=original
    db.style_examples=lambda *args,**kwargs: []
    legacy=make_legacy(db,Bot(),premium=Premium(ready=True))
    legacy.editor=SimpleNamespace(llm=AsyncMock(return_value=original))
    service=PublishingService(legacy,EditorialMemory(db))
    with pytest.raises(ValueError,match="Исходный текст сохранён"):
        asyncio.run(service.fit_caption(8))
    assert db.updated == {} and db.row["text"] == original
