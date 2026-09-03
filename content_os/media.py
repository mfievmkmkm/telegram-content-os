import html
import re
from urllib.parse import urljoin

import aiohttp


META_IMAGE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image(?::src)?)["\'][^>]+content=["\']([^"\']+)',
    re.IGNORECASE,
)
META_IMAGE_REVERSED = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image(?::src)?)["\']',
    re.IGNORECASE,
)


async def discover_image(source_url: str) -> str:
    """Return an article preview image. No image-generation API or extra spend."""
    if not source_url or not source_url.startswith(("http://", "https://")):
        return ""
    headers = {"User-Agent": "Mozilla/5.0 ContentOS/1.0"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12), headers=headers) as session:
            async with session.get(source_url, allow_redirects=True) as response:
                if response.status >= 400 or "text/html" not in response.headers.get("Content-Type", ""):
                    return ""
                page = (await response.text(errors="ignore"))[:500_000]
                match = META_IMAGE.search(page) or META_IMAGE_REVERSED.search(page)
                if not match:
                    return ""
                return urljoin(str(response.url), html.unescape(match.group(1).strip()))
    except Exception:
        return ""
