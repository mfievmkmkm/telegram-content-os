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
