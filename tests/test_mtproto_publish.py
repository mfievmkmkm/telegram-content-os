from telethon.tl.types import MessageEntityBold, MessageEntityCustomEmoji
import pytest

from content_os.mtproto_publish import parse_entities, require_custom_emoji_markup

def test_custom_emoji_and_bold_are_preserved():
    text,entities=parse_entities('<tg-emoji emoji-id="5368324170671202286">⚡</tg-emoji> <b>Хук</b>')
    assert text == "⚡ Хук"
    assert any(isinstance(x,MessageEntityCustomEmoji) and x.document_id==5368324170671202286 for x in entities)
    assert any(isinstance(x,MessageEntityBold) for x in entities)

def test_premium_markup_is_mandatory_and_plain_emoji_is_rejected():
    with pytest.raises(RuntimeError,match="нет фирменного"):
        require_custom_emoji_markup("<b>Хук</b>")
    with pytest.raises(RuntimeError,match="обычный emoji"):
        require_custom_emoji_markup('<tg-emoji emoji-id="5368324170671202286">⚡</tg-emoji> Текст 🔥')
    assert require_custom_emoji_markup('<tg-emoji emoji-id="5368324170671202286">⚡</tg-emoji> Текст') == 1


def test_native_poll_serializes_with_premium_entities(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import content_os.mtproto_publish as module
    from telethon.tl.types import InputMediaPoll
    client = SimpleNamespace(connect=AsyncMock(),disconnect=AsyncMock(),is_user_authorized=AsyncMock(return_value=True),send_file=AsyncMock(return_value=SimpleNamespace(id=10)))
    monkeypatch.setattr(module,"StringSession",lambda value: value)
    monkeypatch.setattr(module,"TelegramClient",lambda *args: client)
    publisher=module.PremiumPublisher(SimpleNamespace(publish_via_mtproto=True,telegram_api_id=1,telegram_api_hash="fake",telegram_session="fake"))
    asyncio.run(publisher.send_poll("@test",'<tg-emoji emoji-id="123">💎</tg-emoji> Что проверяешь первым?',["Контекст","Детали"]))
    media=client.send_file.call_args.args[1]
    assert isinstance(media,InputMediaPoll)
    assert media.poll.answers[0].text.text == "Контекст"
    assert len(media.poll.question.entities) == 1
    assert bytes(media)
    client.disconnect.assert_awaited_once()
