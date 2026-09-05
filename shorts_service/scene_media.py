from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from pathlib import Path
import socket
import textwrap
from urllib.parse import urlparse

import aiohttp


@dataclass(frozen=True)
class SceneSpec:
    seconds: float
    visual: str
    screen_text: str
    asset_type: str
    asset_ref: str = ""


def compile_scene_specs(payload: dict, audio_duration: float) -> list[SceneSpec]:
    raw = payload.get("scenes") or []
    specs: list[SceneSpec] = []
    for item in raw:
        try:
            seconds = float(item.get("seconds") or 0)
        except (TypeError, ValueError):
            seconds = 0
        if seconds <= 0:
            continue
        specs.append(SceneSpec(
            seconds=seconds,
            visual=str(item.get("visual") or "").strip(),
            screen_text=str(item.get("screen_text") or "").strip(),
            asset_type=str(item.get("asset_type") or "stock_video").strip().lower(),
            asset_ref=str(item.get("asset_ref") or "").strip(),
        ))
    if not specs:
        return [SceneSpec(max(1.0, audio_duration), str(payload.get("video_subject") or ""), "", "stock_video")]

    total = sum(item.seconds for item in specs)
    scale = audio_duration / total if total > 0 else 1.0
    # Preserve editorial timing proportions while matching the actual synthesized voice.
    return [SceneSpec(max(.75, item.seconds * scale), item.visual, item.screen_text, item.asset_type, item.asset_ref) for item in specs]


def write_text_card_copy(path: Path, scene: SceneSpec) -> None:
    text = scene.screen_text or scene.visual or "Content OS"
    wrapped = "\n".join(textwrap.wrap(" ".join(text.split()), width=24)[:6])
    path.write_text(wrapped, "utf-8")


def text_card_filter(textfile: Path, channel: str) -> str:
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    label = "GIFTS INTELLIGENCE" if channel == "gifts" else "LIGA PROGRESS"
    # textfile avoids escaping Russian copy inside the ffmpeg filter string.
    return (
        "scale=720:1280,"
        "drawbox=x=40:y=360:w=640:h=560:color=black@0.38:t=fill,"
        f"drawtext=fontfile={font}:text='{label}':fontsize=27:fontcolor=white@0.72:x=(w-text_w)/2:y=405,"
        f"drawtext=fontfile={font}:textfile='{textfile}':fontsize=52:fontcolor=white:"
        "x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=16:fix_bounds=true,"
        "fps=25"
    )


def image_filter() -> str:
    return (
        "scale=760:1352:force_original_aspect_ratio=increase,"
        "crop=720:1280:(iw-ow)/2:(ih-oh)/2,"
        "eq=contrast=1.03:saturation=1.05,fps=25"
    )


def _public_https_url(value: str) -> bool:
    parsed = urlparse((value or "").strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_global
    except ValueError:
        pass
    try:
        addresses = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        # DNS can be unavailable in isolated tests; reject unresolved hosts at runtime.
        return False
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address[4][0])
        except ValueError:
            return False
        if not ip.is_global:
            return False
    return bool(addresses)


async def download_image_asset(url: str, destination: Path, max_bytes: int = 8 * 1024 * 1024) -> Path:
    """Download one public HTTPS image with SSRF/size/content-type guards."""
    if not _public_https_url(url):
        raise ValueError("asset_ref must be a public HTTPS URL")
    timeout = aiohttp.ClientTimeout(total=25, connect=8)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, allow_redirects=False) as response:
            if response.status >= 400:
                raise RuntimeError(f"asset HTTP {response.status}")
            content_type = (response.headers.get("content-type") or "").split(";", 1)[0].lower()
            if content_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise ValueError(f"unsupported image content type: {content_type or 'unknown'}")
            declared = int(response.headers.get("content-length") or 0)
            if declared and declared > max_bytes:
                raise ValueError("image asset is too large")
            data = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise ValueError("image asset is too large")
    destination.write_bytes(data)
    return destination


IMAGE_ASSET_TYPES = {"brand_card", "screenshot", "meme", "market_chart", "generated_image", "user_asset"}
SUPPORTED_ASSET_TYPES = {"stock_video", "text_scene", *IMAGE_ASSET_TYPES}
