from __future__ import annotations

import hashlib
import io

from . import brand_cards
from .formatting import plain_text


SCENE_LAYOUTS = (brand_cards._cinematic, brand_cards._photo_split, brand_cards._number_poster)
LAYOUT_KEYS = ("cinematic", "photo_split", "number_poster", "cinematic_alt", "photo_split_alt", "number_poster_alt", "cinematic_bold", "photo_split_bold")
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
        scene = "3d_fomo_cart.webp" if format_key == "мем" else brand_cards._pick_gift_scene(plain_text(post_text), seed)
    elif channel == "liga":
        scene = brand_cards.LIGA_SCENES[seed % len(brand_cards.LIGA_SCENES)] if format_key == "мем" else brand_cards._pick_liga_scene(plain_text(post_text), seed)
    else:
        raise ValueError(f"Unknown channel: {channel}")

    # Page two/three deliberately moves to another object in the same 3D brand
    # world. This makes “Ещё 3” a genuinely fresh art direction, not a recolor.
    pool = brand_cards.SCENES if channel == "gifts" else brand_cards.LIGA_SCENES
    if variant >= len(SCENE_LAYOUTS):
        scene = pool[(pool.index(scene) + variant // len(SCENE_LAYOUTS)) % len(pool)]

    # Every alternative is built over a real 3D object scene. Higher variants
    # deliberately rotate the composition instead of falling back to old cards.
    image = SCENE_LAYOUTS[variant % len(SCENE_LAYOUTS)](lines, seed, scene, channel)
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def preview_variants(channel: str, post_text: str, format_key: str, count: int = 3, offset: int = 0) -> list[bytes]:
    """Return a page of alternatives; callers can request “ещё 3” without repeats."""
    start = max(0, min(int(offset), len(LAYOUT_KEYS) - 1))
    size = max(1, min(int(count), 3))
    return [render_card(channel, post_text, format_key, variant=index) for index in range(start, min(len(LAYOUT_KEYS), start + size))]
