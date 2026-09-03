from telethon.tl.types import MessageEntityBold, MessageEntityCustomEmoji
from content_os.mtproto_publish import parse_entities

def test_custom_emoji_and_bold_are_preserved():
    text,entities=parse_entities('<tg-emoji emoji-id="5368324170671202286">⚡</tg-emoji> <b>Хук</b>')
    assert text == "⚡ Хук"
    assert any(isinstance(x,MessageEntityCustomEmoji) and x.document_id==5368324170671202286 for x in entities)
    assert any(isinstance(x,MessageEntityBold) for x in entities)
