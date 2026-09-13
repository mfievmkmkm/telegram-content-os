import io, re
from telethon import TelegramClient
from telethon.extensions import html as telethon_html
from telethon.sessions import StringSession
from telethon.tl.types import MessageEntityCustomEmoji

CUSTOM=re.compile(r'<tg-emoji emoji-id="(\d+)">([^<]+)</tg-emoji>')
PLAIN_EMOJI=re.compile(
    "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF]"
    "[\uFE0F\u200D\U0001F3FB-\U0001F3FF]*"
)


def require_custom_emoji_markup(value):
    """Reject plain/missing emoji before opening an MTProto connection."""
    tags=CUSTOM.findall(value or "")
    if not tags:
        raise RuntimeError(
            "В посте нет фирменного Premium emoji. Установи единый набор командой /emojipack all"
        )
    without_custom=CUSTOM.sub("",value or "")
    if PLAIN_EMOJI.search(without_custom):
        raise RuntimeError(
            "В посте остался обычный emoji. Публикация остановлена, чтобы не ломать фирменный стиль"
        )
    if len(tags)>3:
        raise RuntimeError("В посте больше трёх Premium emoji")
    return len(tags)

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
    async def probe(self,channel):
        if not self.ready: return False,"переменные MTProto не заполнены"
        client=TelegramClient(StringSession(self.settings.telegram_session),self.settings.telegram_api_id,self.settings.telegram_api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized(): return False,"сессия Telegram не авторизована"
            entity=await client.get_entity(channel)
            permissions=await client.get_permissions(entity,"me")
            if getattr(entity,"broadcast",False) and not (getattr(permissions,"is_admin",False) or getattr(permissions,"is_creator",False)):
                return False,"Premium-аккаунт не администратор канала"
            return True,"доступ к каналу подтверждён"
        except Exception as exc: return False,f"{type(exc).__name__}: {str(exc)[:160]}"
        finally: await client.disconnect()
    async def send(self,channel,html_text,image=None):
        if not self.ready:
            raise RuntimeError("Premium MTProto не настроен")
        expected=require_custom_emoji_markup(html_text)
        text,entities=parse_entities(html_text)
        actual=sum(isinstance(item,MessageEntityCustomEmoji) for item in entities)
        if actual!=expected:
            raise RuntimeError("Не удалось собрать Premium emoji entities")
        client=TelegramClient(StringSession(self.settings.telegram_session),self.settings.telegram_api_id,self.settings.telegram_api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized(): raise RuntimeError("MTProto session is not authorized")
            if image:
                file=io.BytesIO(image); file.name="gifts-intelligence.png"
                return await client.send_file(channel,file,caption=text,formatting_entities=entities)
            return await client.send_message(channel,text,formatting_entities=entities,link_preview=False)
        finally: await client.disconnect()
