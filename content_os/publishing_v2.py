from __future__ import annotations

import html
import logging
from datetime import datetime

from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from .formatting import plain_text, telegram_html
from .visual_renderer import render_card


log = logging.getLogger("content-os.publish-v2")


class PublishingService:
    """Publish a reviewed draft without silently dropping its chosen visual.

    Telegram captions are short. For long editorial posts the selected card is sent
    as a visual opener and the full post follows as a text message. The text message
    remains the analytics anchor (`published_message_id`).
    """

    def __init__(self, legacy, editorial_memory):
        self.legacy = legacy
        self.db = legacy.db
        self.memory = editorial_memory

    async def publish(self, draft_id: int | str):
        legacy = self.legacy
        draft = self.db.draft(int(draft_id))
        if not draft:
            raise KeyError(f"Draft {draft_id} not found")
        channel = legacy.settings.channels[draft["channel_key"]]
        sales_markup, sales_link = await self._sales_cta(draft)
        rendered = legacy.render(draft["channel_key"], draft["text"]) + (sales_link or "")
        bot_rendered = telegram_html(draft["text"]) + (sales_link or "")

        selected = self.memory.selected_variant(draft_id)
        wants_card = selected is not None or (
            legacy.use_gift_card(draft_id) if draft["channel_key"] == "gifts" else legacy.use_liga_card(draft_id)
        )
        card_bytes = None
        if wants_card:
            try:
                card_bytes = render_card(
                    draft["channel_key"],
                    draft["text"],
                    draft["format_key"],
                    selected if selected is not None else self.memory.variant_for_text(draft["text"]),
                )
            except Exception:
                log.exception("Could not render selected card for draft %s", draft_id)

        premium_error = None
        sent = None
        mode = "bot"
        text_len = len(plain_text(draft["text"]))

        if card_bytes and text_len <= 1000 and not legacy.premium_publisher.ready:
            sent = await legacy.bot.send_photo(
                channel,
                BufferedInputFile(card_bytes, filename=f"{draft['channel_key']}-{draft_id}.png"),
                caption=bot_rendered,
                parse_mode=ParseMode.HTML,
                reply_markup=sales_markup,
            )
        else:
            # For long posts the visual is never sacrificed just because Telegram's
            # media caption is too small. It becomes a clean editorial opener.
            if card_bytes:
                await legacy.bot.send_photo(
                    channel,
                    BufferedInputFile(card_bytes, filename=f"{draft['channel_key']}-{draft_id}.png"),
                )
            elif draft["channel_key"] != "gifts":
                source_image = await legacy.discover_image(draft["source_url"] or "")
                if source_image:
                    try:
                        await legacy.bot.send_photo(channel, source_image)
                    except Exception:
                        log.info("Source image unavailable during publish: %s", source_image)

            if legacy.premium_publisher.ready:
                try:
                    # Text-only premium publish keeps custom emoji while the visual
                    # stays independent of caption limits.
                    sent = await legacy.premium_publisher.send(channel, rendered, None)
                    mode = "premium"
                except Exception as exc:
                    premium_error = f"{type(exc).__name__}: {str(exc)[:220]}"
                    log.exception("Premium publish failed; falling back to Bot API")
            if sent is None:
                sent = await legacy.bot.send_message(
                    channel,
                    bot_rendered,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=sales_markup,
                )
                mode = "bot"

        message_id = getattr(sent, "message_id", None) or getattr(sent, "id", None)
        if not message_id:
            raise RuntimeError("Telegram отправил пост, но не вернул ID сообщения")
        self.db.update(
            int(draft_id),
            status="published",
            published_at=datetime.now(legacy.settings.timezone).isoformat(),
            published_message_id=message_id,
        )
        return mode, premium_error

    async def _sales_cta(self, draft):
        legacy = self.legacy
        if not legacy.settings.shop_cta_every or int(draft["id"]) % legacy.settings.shop_cta_every != 0:
            return None, None
        me = await (legacy.shop_bot or legacy.bot).get_me()
        slug = "service_liga" if draft["channel_key"] == "liga" else "service_gifts"
        label = "Разобрать мой эпизод" if draft["channel_key"] == "liga" else "Проверить мой Gift"
        sales_url = f"https://t.me/{me.username}?start={slug}"
        if legacy.premium_publisher.ready:
            return None, f'\n\n<a href="{sales_url}"><b>{html.escape(label)} →</b></a>'
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, url=sales_url)]]), None


def install_publishing(legacy, editorial_memory):
    service = PublishingService(legacy, editorial_memory)
    legacy.publish = service.publish
    return service
