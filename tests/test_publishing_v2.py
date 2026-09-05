import asyncio
from types import SimpleNamespace
from zoneinfo import ZoneInfo

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
            text="Смотри не только на floor\n\n" + ("Контекст важнее одной цифры. " * 70),
            source_url="",
        )
        self.updated = {}
    def get(self, key): return self.settings.get(key)
    def set(self, key, value): self.settings[key] = value
    def draft(self, draft_id): return self.row if int(draft_id) == 8 else None
    def update(self, draft_id, **fields): self.updated.update(fields)


class Bot:
    def __init__(self): self.photos = []; self.messages = []
    async def send_photo(self, channel, photo, **kwargs):
        self.photos.append((channel, kwargs)); return SimpleNamespace(message_id=91)
    async def send_message(self, channel, text, **kwargs):
        self.messages.append((channel, text, kwargs)); return SimpleNamespace(message_id=92)
    async def get_me(self): return SimpleNamespace(username="shopbot")


class Premium:
    ready = False


async def no_image(url): return None


def test_long_post_keeps_selected_card_and_analytics_anchor():
    db = DB(); memory = EditorialMemory(db); memory.select_variant(8, 1, db.row["text"])
    bot = Bot()
    legacy = SimpleNamespace(
        db=db,
        bot=bot,
        shop_bot=None,
        premium_publisher=Premium(),
        settings=SimpleNamespace(
            channels={"gifts": "@gifts"},
            timezone=ZoneInfo("UTC"),
            shop_cta_every=0,
        ),
        render=lambda channel, text: text,
        use_gift_card=lambda draft_id: True,
        use_liga_card=lambda draft_id: True,
        discover_image=no_image,
    )
    service = PublishingService(legacy, memory)
    mode, error = asyncio.run(service.publish(8))
    assert mode == "bot"
    assert error is None
    assert len(bot.photos) == 1
    assert len(bot.messages) == 1
    assert db.updated["published_message_id"] == 92
    assert db.updated["status"] == "published"
