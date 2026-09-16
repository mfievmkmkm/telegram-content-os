from __future__ import annotations

import html
import logging
from datetime import datetime

from .campaigns import CampaignRef
from .content_quality import build_fingerprint
from .formatting import plain_text
from .growth.cta import telegram_deep_link
from .mtproto_publish import require_custom_emoji_markup
from .visual_renderer import render_card
from .remix_store import load_poll
from .mtproto_publish import parse_entities
from .formatting import clean_generated_post, decorate_post
from .hooks import score_hook
from .channels import CHANNELS


log = logging.getLogger("content-os.publish-v2")
CAPTION_BUDGET = 1000


class CaptionTooLongError(ValueError):
    pass


def caption_length(rendered):
    text, _ = parse_entities(rendered)
    return len(text.encode("utf-16-le")) // 2


def caption_keyboard(draft_id):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✂️ Подогнать под карточку", callback_data=f"publishfit:{draft_id}")],
        [InlineKeyboardButton(text="‹ К посту", callback_data=f"back:{draft_id}")],
    ])


class PublishingService:
    """Publish a reviewed draft as one complete Telegram post.

    A branded card and its copy must never be split into two channel messages. Old
    drafts that no longer fit Telegram's caption limit are rejected before any
    network side effect so an editor can shorten them deliberately.
    """

    def __init__(self, legacy, editorial_memory):
        self.legacy = legacy
        self.db = legacy.db
        self.memory = editorial_memory

    async def fit_caption(self, draft_id):
        from .director_service import ContentDirectorService
        draft = self.db.draft(int(draft_id))
        if not draft or dict(draft).get("status") in {"deleted", "published"}:
            raise ValueError("Черновик не найден, удалён или уже опубликован")
        if draft["format_key"] == "remix_poll":
            raise ValueError("У опроса нет подписи к карточке")
        channel = draft["channel_key"]
        _, footer = await self._sales_cta(draft)
        footer = footer or ""
        rendered = self.legacy.render(channel, draft["text"]) + footer
        if caption_length(rendered) <= CAPTION_BUDGET:
            return draft, rendered
        target = max(150, CAPTION_BUDGET - caption_length(footer) - 150)
        director = ContentDirectorService(self.legacy.editor, self.db, self.memory)
        for _ in range(2):
            raw = await self.legacy.editor.llm(CHANNELS[channel]["voice"],
                f"Сократи пост до {target} знаков для подписи к карточке. Сохрани сильный хук, "
                "главную мысль, подтверждённые факты и законченный финал. Не добавляй цифр, "
                "обещаний, ссылок или новых фактов. Убери повторы. Верни только готовый текст.\n\n"
                + draft["text"], .5)
            text = decorate_post(clean_generated_post(raw), channel)
            rendered = self.legacy.render(channel, text) + footer
            candidate = dict(draft)
            candidate.update(text=text, hook_score=score_hook(plain_text(text))[0])
            if caption_length(rendered) <= CAPTION_BUDGET and director.evaluate(candidate).approved:
                current = self.db.draft(int(draft_id))
                if not current or current["text"] != draft["text"] or dict(current).get("status") in {"deleted", "published"}:
                    raise ValueError("Черновик изменился во время сокращения. Открой его заново")
                key = f"v2:caption_original:{draft_id}"
                if not self.db.get(key): self.db.set(key, draft["text"])
                self.db.update(int(draft_id), text=text, hook_score=candidate["hook_score"], status="review", scheduled_at=None)
                return candidate, rendered
            target = max(150, target - 150)
        raise ValueError("Модель не смогла сократить текст без потери качества. Исходный текст сохранён; попробуй ещё раз")

    async def publish(self, draft_id: int | str):
        legacy = self.legacy
        draft = self.db.draft(int(draft_id))
        if not draft:
            raise KeyError(f"Draft {draft_id} not found")
        if dict(draft).get("status") == "deleted":
            raise ValueError("Черновик удалён")
        if dict(draft).get("status") == "published":
            raise ValueError("Этот черновик уже опубликован")
        if not legacy.premium_publisher.ready:
            raise RuntimeError(
                "Premium Publish обязателен. Проверь PUBLISH_VIA_MTPROTO, TELEGRAM_API_ID, "
                "TELEGRAM_API_HASH и TELEGRAM_SESSION_STRING"
            )
        channel = legacy.settings.channels[draft["channel_key"]]
        if draft["format_key"] == "remix_poll":
            poll = load_poll(self.db, draft_id)
            rendered_question = legacy.render(draft["channel_key"], poll["question"])
            sent = await legacy.premium_publisher.send_poll(channel, rendered_question, poll["options"])
            message_id = getattr(sent, "message_id", None) or getattr(sent, "id", None)
            if not message_id:
                raise RuntimeError("Telegram не вернул ID опроса; проверь канал перед повтором")
            self.db.update(int(draft_id), status="published", published_at=datetime.now(legacy.settings.timezone).isoformat(), published_message_id=message_id)
            self.memory.remember_content(draft["channel_key"], build_fingerprint(text=draft["text"], topic=draft["source_title"] or "poll", angle="poll", format_key="remix_poll"), draft["text"], draft_id=draft_id)
            return "premium", None
        _, sales_link = await self._sales_cta(draft)
        rendered = legacy.render(draft["channel_key"], draft["text"]) + (sales_link or "")
        require_custom_emoji_markup(rendered)

        selected = self.memory.selected_variant(draft_id)
        wants_card = selected is not None or (
            legacy.use_gift_card(draft_id) if draft["channel_key"] == "gifts" else legacy.use_liga_card(draft_id)
        )
        text_len = caption_length(rendered)
        if wants_card and text_len > CAPTION_BUDGET:
            raise CaptionTooLongError(
                f"Подпись с оформлением и ссылкой: {text_len} знаков, бюджет карточки — {CAPTION_BUDGET}. "
                "Нажми «Подогнать под карточку»: покажу сокращённую версию перед публикацией"
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
            except Exception as exc:
                log.exception("Could not render selected card for draft %s", draft_id)
                raise RuntimeError("Карточка не собралась; публикация остановлена, попробуй ещё раз") from exc

        try:
            sent = await legacy.premium_publisher.send(channel, rendered, card_bytes)
        except Exception as exc:
            log.exception("Premium publish failed; publication aborted")
            raise RuntimeError(
                f"Premium Publish не сработал; пост не опубликован: {type(exc).__name__}: {str(exc)[:220]}"
            ) from exc

        message_id = getattr(sent, "message_id", None) or getattr(sent, "id", None)
        if not message_id:
            raise RuntimeError("Telegram отправил пост, но не вернул ID сообщения")
        self.db.update(
            int(draft_id),
            status="published",
            published_at=datetime.now(legacy.settings.timezone).isoformat(),
            published_message_id=message_id,
        )
        fingerprint = build_fingerprint(
            text=draft["text"],
            topic=str(draft.get("source_title") or draft["format_key"]) if isinstance(draft, dict) else str(draft["source_title"] or draft["format_key"]),
            angle=str(draft["format_key"]),
            format_key=str(draft["format_key"]),
            visual_type=f"card_v{selected}" if card_bytes and selected is not None else "card" if card_bytes else "source_or_text",
        )
        self.memory.remember_content(draft["channel_key"], fingerprint, draft["text"], draft_id=draft["id"])
        return "premium", None

    async def _sales_cta(self, draft):
        legacy = self.legacy
        if not legacy.settings.shop_cta_every or int(draft["id"]) % legacy.settings.shop_cta_every != 0:
            return None, None

        label = "Разобрать мой эпизод" if draft["channel_key"] == "liga" else "Открыть Gifts Intelligence"
        if legacy.shop_bot:
            me = await legacy.shop_bot.get_me()
            raw_format = str(draft["format_key"] or "").lower()
            format_key = raw_format if raw_format in {"shorts", "meme", "card"} else "post"
            ref = CampaignRef(
                project=str(draft["channel_key"]),
                content_id=int(draft["id"]),
                format_key=format_key,
                offer="liga-episode" if draft["channel_key"] == "liga" else "gifts-access",
                campaign="organic",
            )
            tracked = telegram_deep_link(me.username, ref, label)
            sales_url = tracked.url
        else:
            # Backward-compatible fallback when Shop has not been split into its own bot.
            me = await legacy.bot.get_me()
            slug = "service_liga" if draft["channel_key"] == "liga" else "service_gifts"
            sales_url = f"https://t.me/{me.username}?start={slug}"

        return None, f'\n\n<a href="{sales_url}"><b>{html.escape(label)} →</b></a>'


def install_publishing(legacy, editorial_memory):
    from aiogram import F, Router
    from aiogram.enums import ParseMode
    import asyncio
    service = PublishingService(legacy, editorial_memory)
    router = Router(name="caption-fit")
    lock = asyncio.Lock()

    @router.callback_query(F.data.startswith("publishfit:"))
    async def fit(c):
        if not legacy.admin(c): return
        raw = c.data.rsplit(":", 1)[-1]
        if not raw.isdigit(): return await c.answer("Некорректный черновик", show_alert=True)
        await c.answer("Подгоняю текст под карточку…")
        try:
            async with lock:
                _, rendered = await service.fit_caption(int(raw))
            await c.message.answer(
                f"<b>Подпись готова · {caption_length(rendered)}/{CAPTION_BUDGET}</b>\n"
                f"Проверь сокращённый текст и нажми «В канал» или выбери время заново.\n\n{rendered}",
                parse_mode=ParseMode.HTML, reply_markup=legacy.keyboard(int(raw)),
            )
        except Exception as exc:
            log.exception("Caption fit failed")
            await c.message.answer(f"❌ {html.escape(str(exc)[:350])}", parse_mode=ParseMode.HTML, reply_markup=caption_keyboard(raw))

    legacy.dp.include_router(router)
    legacy.publish = service.publish
    return service
