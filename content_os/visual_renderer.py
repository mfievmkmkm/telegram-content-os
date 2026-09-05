from __future__ import annotations

import hashlib
import io

from PIL import Image, ImageDraw

from . import brand_cards
from .formatting import plain_text


SCENE_LAYOUTS = (brand_cards._cinematic, brand_cards._photo_split, brand_cards._number_poster)
FLAT_LAYOUTS = (
    brand_cards._dashboard,
    brand_cards._meme,
    brand_cards._dossier,
    brand_cards._editorial,
    brand_cards._spotlight,
)
LAYOUT_KEYS = ("cinematic", "photo_split", "number_poster", "dashboard", "chat_meme", "dossier", "editorial", "spotlight")
PALETTES = {
    "gifts": ((176, 255, 0), (91, 223, 255), (202, 112, 255), (255, 186, 51), (255, 79, 96)),
    "liga": ((100, 255, 171), (67, 205, 255), (255, 177, 45), (180, 139, 255), (242, 247, 250)),
}


def layout_key(variant: int) -> str:
    return LAYOUT_KEYS[max(0, min(int(variant), len(LAYOUT_KEYS) - 1))]


def fresh_page_offset(recent_keys) -> int:
    """Open the least recently used group instead of always showing A/B/C first."""
    recent = list(recent_keys or ())[-8:]
    pages = (0, 3, 6)
    return min(
        pages,
        key=lambda offset: sum(
            (len(recent) - recent.index(key)) if key in recent else 0
            for key in LAYOUT_KEYS[offset:offset + 3]
        ),
    )


def render_card(channel: str, post_text: str, format_key: str, variant: int = 0) -> bytes:
    """Render a stable, genuinely different visual alternative.

    A/B/C rotate both composition and deterministic scene seed. This guarantees
    that asking for alternatives changes the design, not merely an invisible seed.
    No extra LLM call is required.
    """
    variant = max(0, min(int(variant), len(LAYOUT_KEYS) - 1))
    lines = brand_cards._lines(post_text)
    salt = f"{channel}:{format_key}:variant:{variant}:{plain_text(post_text)}"
    seed = int(hashlib.sha256(salt.encode("utf-8")).hexdigest()[:8], 16) + variant * 97
    if channel == "gifts":
        scene = "fomo_meme.webp" if format_key == "мем" else brand_cards._pick_gift_scene(plain_text(post_text), seed)
    elif channel == "liga":
        scene = ("empty_bench.webp", "golden_bench.webp")[seed % 2] if format_key == "мем" else brand_cards._pick_liga_scene(plain_text(post_text), seed)
    else:
        raise ValueError(f"Unknown channel: {channel}")

    if variant < len(SCENE_LAYOUTS):
        image = SCENE_LAYOUTS[variant](lines, seed, scene, channel)
    else:
        renderer = FLAT_LAYOUTS[variant - len(SCENE_LAYOUTS)]
        image = Image.new("RGB", (1080, 1080))
        accent = PALETTES[channel][seed % len(PALETTES[channel])]
        renderer(ImageDraw.Draw(image), lines, accent, seed, channel)
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def preview_variants(channel: str, post_text: str, format_key: str, count: int = 3, offset: int = 0) -> list[bytes]:
    """Return a page of alternatives; callers can request “ещё 3” without repeats."""
    start = max(0, min(int(offset), len(LAYOUT_KEYS) - 1))
    size = max(1, min(int(count), 3))
    return [render_card(channel, post_text, format_key, variant=index) for index in range(start, min(len(LAYOUT_KEYS), start + size))]
