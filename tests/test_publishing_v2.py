import asyncio
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from content_os.editorial_memory import EditorialMemory
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
    def __init__(self, ready=False): self.ready = ready; self.sent = []
    async def send(self, channel, text, image=None):
        self.sent.append((channel, text, image)); return SimpleNamespace(id=93)


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
        render=lambda channel, text: text,
        use_gift_card=lambda draft_id: True,
        use_liga_card=lambda draft_id: True,
        discover_image=no_image,
    )


def test_card_and_caption_are_one_bot_message():
    db = DB(); memory = EditorialMemory(db); memory.select_variant(8, 1, db.row["text"])
    bot = Bot()
    service = PublishingService(make_legacy(db, bot), memory)
    mode, error = asyncio.run(service.publish(8))
    assert mode == "bot"
    assert error is None
    assert len(bot.photos) == 1
    assert len(bot.messages) == 0
    assert bot.photos[0][1]["caption"]
    assert db.updated["published_message_id"] == 91
    assert db.updated["status"] == "published"


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
    bot = Bot(); service = PublishingService(make_legacy(db, bot), memory)
    with pytest.raises(RuntimeError, match="Короче"):
        asyncio.run(service.publish(8))
    assert bot.photos == [] and bot.messages == []
    assert db.updated == {}


def test_publish_cta_uses_campaign_payload_when_shop_bot_exists():
    db = DB(); memory = EditorialMemory(db); bot = Bot("editorbot"); shop = Bot("shopbot")
    service = PublishingService(make_legacy(db, bot, shop_bot=shop, shop_cta_every=4), memory)
    markup, link = asyncio.run(service._sales_cta(db.row))
    assert link is None
    url = markup.inline_keyboard[0][0].url
    assert url.startswith("https://t.me/shopbot?start=c_g_8_p_gifts-access_organic")
    assert "service_gifts" not in url
