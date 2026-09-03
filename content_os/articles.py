import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup


def extract_article(page:str):
    soup=BeautifulSoup(page,"html.parser")
    for node in soup.select("script,style,noscript,nav,footer,header,aside"): node.decompose()
    title=(soup.title.get_text(" ",strip=True) if soup.title else "Материал")[:300]
    description=soup.select_one('meta[name="description"],meta[property="og:description"]')
    parts=[description.get("content","").strip()] if description else []
    parts.extend(node.get_text(" ",strip=True) for node in soup.select("article p,main p,p") if len(node.get_text(" ",strip=True))>45)
    seen=[]
    for part in parts:
        if part and part not in seen: seen.append(part)
    return title,"\n".join(seen)[:7000]

async def validate_public_url(url:str):
    parsed=urlparse(url)
    if parsed.scheme not in {"http","https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Нужна обычная публичная http/https-ссылка")
    records=await asyncio.to_thread(socket.getaddrinfo,parsed.hostname,parsed.port or (443 if parsed.scheme=="https" else 80),0,socket.SOCK_STREAM)
    if any(not ipaddress.ip_address(item[4][0]).is_global for item in records): raise ValueError("Локальные адреса запрещены")

async def fetch_article(url:str):
    current=url; headers={"User-Agent":"Mozilla/5.0 ContentOS/1.0"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40),headers=headers) as session:
        for _ in range(5):
            await validate_public_url(current)
            async with session.get(current,allow_redirects=False) as response:
                if 300<=response.status<400 and response.headers.get("Location"):
                    current=urljoin(current,response.headers["Location"]); continue
                if response.status>=400: raise RuntimeError(f"Сайт вернул HTTP {response.status}")
                if "html" not in response.headers.get("Content-Type",""): raise ValueError("По ссылке нет читаемой статьи")
                return (*extract_article(await response.text(errors="ignore")),current)
    raise ValueError("Слишком много перенаправлений")
