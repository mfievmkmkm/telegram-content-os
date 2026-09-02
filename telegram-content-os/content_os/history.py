import re
from dataclasses import dataclass

import aiohttp
from bs4 import BeautifulSoup


HISTORY_SOURCES = [
    ("liga", "LigaProgress", "own"),
    ("liga", "prrlig", "own"),
    ("liga", "FootballTrain14", "radar"),
    ("liga", "instinctxfootball", "radar"),
    ("gifts", "GiftsIntelligence", "own"),
    ("gifts", "leanhustle_crypto", "radar"),
    ("gifts", "getSendGifts", "radar"),
]


@dataclass
class ImportResult:
    channel: str
    role: str
    found: int
    added: int
    error: str = ""


def parse_views(raw: str):
    raw=raw.strip().upper().replace(",", ".")
    try:
        if raw.endswith("K"): return int(float(raw[:-1])*1_000)
        if raw.endswith("M"): return int(float(raw[:-1])*1_000_000)
        return int(raw.replace(" ",""))
    except ValueError: return None


def parse_preview(page: str, channel: str):
    soup=BeautifulSoup(page,"html.parser"); posts=[]
    for node in soup.select(".tgme_widget_message"):
        data_post=node.get("data-post","")
        match=re.search(r"/(\d+)$",data_post)
        text_node=node.select_one(".tgme_widget_message_text")
        if not match or not text_node: continue
        views=node.select_one(".tgme_widget_message_views"); time=node.select_one("time")
        posts.append({"id":int(match.group(1)),"text":text_node.get_text("\n",strip=True),
                      "views":parse_views(views.get_text(strip=True)) if views else None,
                      "posted_at":time.get("datetime") if time else None})
    return posts


class HistoryImporter:
    def __init__(self, database): self.db=database

    async def sync_one(self, channel_key, source_channel, role):
        url=f"https://t.me/s/{source_channel}"
        try:
            headers={"User-Agent":"Mozilla/5.0 ContentOS/1.0"}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30),headers=headers) as session:
                async with session.get(url) as response:
                    if response.status>=400: raise RuntimeError(f"HTTP {response.status}")
                    page=await response.text()
            posts=parse_preview(page,source_channel); added=0
            for post in posts:
                added+=self.db.save_channel_post(channel_key,source_channel,role,post["id"],post["text"],post["views"],post["posted_at"])
            return ImportResult(source_channel,role,len(posts),added)
        except Exception as exc:
            return ImportResult(source_channel,role,0,0,str(exc)[:120])

    async def sync_all(self):
        results=[]
        for args in HISTORY_SOURCES: results.append(await self.sync_one(*args))
        return results
