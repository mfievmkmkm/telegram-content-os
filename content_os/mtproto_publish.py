import io, re
from telethon import TelegramClient
from telethon.extensions import html as telethon_html
from telethon.sessions import StringSession
from telethon.tl.types import MessageEntityCustomEmoji

CUSTOM=re.compile(r'<tg-emoji emoji-id="(\d+)">([^<]+)</tg-emoji>')

def parse_entities(value):
    custom=[]
    def unwrap(match): custom.append((match.group(2),int(match.group(1)))); return match.group(2)
    text,entities=telethon_html.parse(CUSTOM.sub(unwrap,value))
    cursor=0
    for fallback,document_id in custom:
        index=text.find(fallback,cursor)
        if index<0: continue
        offset=len(text[:index].encode("utf-16-le"))//2; length=len(fallback.encode("utf-16-le"))//2
        entities.append(MessageEntityCustomEmoji(offset,length,document_id)); cursor=index+len(fallback)
    return text,entities

class PremiumPublisher:
    def __init__(self,settings): self.settings=settings
    @property
    def ready(self):
        return bool(self.settings.publish_via_mtproto and self.settings.telegram_api_id and self.settings.telegram_api_hash and self.settings.telegram_session)
    async def send(self,channel,html_text,image=None):
        text,entities=parse_entities(html_text); client=TelegramClient(StringSession(self.settings.telegram_session),self.settings.telegram_api_id,self.settings.telegram_api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized(): raise RuntimeError("MTProto session is not authorized")
            if image:
                file=io.BytesIO(image); file.name="gifts-intelligence.png"
                return await client.send_file(channel,file,caption=text,formatting_entities=entities)
            return await client.send_message(channel,text,formatting_entities=entities,link_preview=False)
        finally: await client.disconnect()
