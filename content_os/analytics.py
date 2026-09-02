import logging

from telethon import TelegramClient
from telethon.sessions import StringSession

log=logging.getLogger("content-os.analytics")

def reaction_count(message):
    reactions=getattr(message,"reactions",None)
    return sum(getattr(item,"count",0) for item in getattr(reactions,"results",[]) or [])

class AnalyticsCollector:
    def __init__(self,settings,database): self.settings,self.db=settings,database

    @property
    def ready(self):
        return bool(self.settings.telegram_api_id and self.settings.telegram_api_hash and self.settings.telegram_session)

    async def sync(self):
        if not self.ready: return {"updated":0,"errors":["MTProto не настроен"]}
        updated=0; errors=[]
        client=TelegramClient(StringSession(self.settings.telegram_session),self.settings.telegram_api_id,self.settings.telegram_api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized(): return {"updated":0,"errors":["Telegram session не авторизована"]}
            for draft in self.db.published_for_metrics():
                try:
                    channel=self.settings.channels[draft["channel_key"]]
                    message=await client.get_messages(channel,ids=draft["published_message_id"])
                    if not message: continue
                    self.db.save_metrics(draft["id"],int(message.views or 0),reaction_count(message),int(message.forwards or 0)); updated+=1
                except Exception as exc: errors.append(f"#{draft['id']}: {str(exc)[:100]}")
        finally: await client.disconnect()
        return {"updated":updated,"errors":errors}

    def report(self):
        rows=self.db.analytics_summary()
        if not rows: return "Статистики пока нет. Опубликуй посты и запусти /analytics."
        lines=[]
        for i,row in enumerate(rows,1):
            hook=next((x.strip() for x in row["text"].splitlines() if x.strip()),"")[:65]
            lines.append(f"{i}. {row['channel_key']} · {row['format_key']} · хук {row['hook_score']}/5\n{hook}\n👁 {row['views']} · ❤️ {row['reactions']} · ↗️ {row['forwards']} · ER {row['engagement']:.2f}%")
        return "🏆 Лучшие публикации\n\n"+"\n\n".join(lines)
