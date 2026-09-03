"""Run locally. Never paste the resulting session into chat or GitHub."""
import asyncio, getpass
from telethon import TelegramClient
from telethon.sessions import StringSession

async def main():
    api_id=int(input("TELEGRAM_API_ID: ").strip())
    api_hash=getpass.getpass("TELEGRAM_API_HASH: ").strip()
    phone=input("Phone (+...): ").strip()
    client=TelegramClient(StringSession(),api_id,api_hash)
    await client.start(phone=phone)
    print("\nTELEGRAM_SESSION_STRING (save only in Railway):\n")
    print(client.session.save())
    await client.disconnect()

if __name__=="__main__": asyncio.run(main())
