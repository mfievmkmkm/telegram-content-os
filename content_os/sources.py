import html
import math
import random
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse

import feedparser


def google_news(query: str, language="ru", country="RU") -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={language}&gl={country}&ceid={country}:{language}"


SOURCE_REGISTRY = {
    "liga": [
        {"url":"https://unknownfootball-volodin.blogspot.com/feeds/posts/default?alt=rss","name":"Неизвестный футбол","trust":4,"kind":"ideas"},
        {"url":google_news('site:fifatrainingcentre.com football training'),"name":"FIFA Training Centre","trust":5,"kind":"training"},
        {"url":google_news('site:uefa.com football technical analysis'),"name":"UEFA","trust":5,"kind":"analysis"},
        {"url":google_news('site:thecoachesvoice.com football tactics OR training',"en","US"),"name":"Coaches Voice","trust":4,"kind":"analysis"},
        {"url":google_news('football player development training psychology',"en","US"),"name":"Football EN","trust":3,"kind":"discovery"},
        {"url":google_news('футбол тренировка техника игрок психология'),"name":"Football RU","trust":3,"kind":"discovery"},
        {"url":"https://github.com/SoccerNet/sn-gamestate/releases.atom","name":"SoccerNet GameState","trust":4,"kind":"github"},
        {"url":"https://github.com/roboflow/sports/releases.atom","name":"Roboflow Sports","trust":4,"kind":"github"},
    ],
    "gifts": [
        {"url":"https://telegram.org/blog/rss","name":"Telegram Blog","trust":5,"kind":"official"},
        {"url":google_news('Telegram collectible gifts TON'),"name":"Gifts RU","trust":3,"kind":"discovery"},
        {"url":google_news('Telegram Gifts marketplace TON NFT',"en","US"),"name":"Gifts EN","trust":3,"kind":"discovery"},
        {"url":google_news('site:ton.org Telegram Gifts'),"name":"TON","trust":5,"kind":"official"},
        {"url":google_news('Portals Telegram Gifts marketplace'),"name":"Portals radar","trust":3,"kind":"market"},
        {"url":"https://github.com/GIFT-ASSET/gift_asset_api/releases.atom","name":"Gift Asset","trust":4,"kind":"github"},
        {"url":"https://github.com/bohd4nx/gifts-tracker/releases.atom","name":"Gifts Tracker","trust":4,"kind":"github"},
    ],
}

KEYWORDS = {
    "liga": ("игрок","футбол","тренер","матч","трениров","техник","тактик","player","football","soccer","coach","training","skill"),
    "gifts": ("telegram","gift","подар","ton","collectible","fragment","portals","nft","market","floor","model","backdrop"),
}
HOOK_SIGNALS = ("почему","ошибка","секрет","запрет","никогда","впервые","против","сломал","потерял","вместо","how","why","mistake","first")


def clean_markup(value: str) -> str:
    value=re.sub(r"<[^>]+>"," ",html.unescape(value or ""))
    return re.sub(r"\s+"," ",value).strip()


def entry_datetime(entry):
    raw=entry.get("published") or entry.get("updated")
    if not raw: return None
    try:
        value=parsedate_to_datetime(raw)
        return value.replace(tzinfo=value.tzinfo or timezone.utc)
    except (TypeError,ValueError,OverflowError): return None


def score_item(item: dict, channel_key: str, now=None) -> int:
    now=now or datetime.now(timezone.utc); haystack=f"{item['title']} {item['summary']}".lower(); score=item["trust"]*2
    score+=min(6,sum(1 for word in KEYWORDS[channel_key] if word in haystack))
    score+=min(3,sum(1 for word in HOOK_SIGNALS if word in haystack))
    published=item.get("published_at")
    if published:
        hours=max(0,(now-published.astimezone(timezone.utc)).total_seconds()/3600)
        score+=max(0,6-math.floor(hours/24))
    if len(item["summary"])>180: score+=1
    if item["kind"]=="github": score+=2
    return score


def collect_items(channel_key: str) -> list[dict]:
    items=[]
    for source in SOURCE_REGISTRY[channel_key]:
        feed=feedparser.parse(source["url"])
        for entry in feed.entries[:15]:
            url=entry.get("link","").strip(); title=clean_markup(entry.get("title","")); summary=clean_markup(entry.get("summary",""))[:3500]
            if not url or not title: continue
            item={"title":title,"url":url,"summary":summary,"source_name":source["name"],"trust":source["trust"],
                  "kind":source["kind"],"published_at":entry_datetime(entry),"domain":urlparse(url).netloc}
            item["score"]=score_item(item,channel_key); items.append(item)
    random.shuffle(items); items.sort(key=lambda x:x["score"],reverse=True)
    return items
