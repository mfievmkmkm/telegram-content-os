from __future__ import annotations

import hashlib
import io

from . import brand_cards
from .formatting import plain_text


LAYOUTS = (brand_cards._cinematic, brand_cards._photo_split, brand_cards._number_poster)


def render_card(channel: str, post_text: str, format_key: str, variant: int = 0) -> bytes:
    """Render a stable, genuinely different visual alternative.

    A/B/C rotate both composition and deterministic scene seed. This guarantees
    that asking for alternatives changes the design, not merely an invisible seed.
    No extra LLM call is required.
    """
    variant = max(0, min(int(variant), 8))
    lines = brand_cards._lines(post_text)
    salt = f"{channel}:{format_key}:variant:{variant}:{plain_text(post_text)}"
    seed = int(hashlib.sha256(salt.encode("utf-8")).hexdigest()[:8], 16) + variant * 97
    if channel == "gifts":
        scene = "fomo_meme.webp" if format_key == "мем" else brand_cards._pick_gift_scene(plain_text(post_text), seed)
    elif channel == "liga":
        scene = ("empty_bench.webp", "golden_bench.webp")[seed % 2] if format_key == "мем" else brand_cards._pick_liga_scene(plain_text(post_text), seed)
    else:
        raise ValueError(f"Unknown channel: {channel}")

    preferred = {
        "мем": 0,
        "рынок_за_минуту": 2,
        "data_desk": 1,
        "разбор_ошибки": 0,
        "course_insight": 1,
        "обучение": 1,
        "сигнал_или_шум": 2,
        "тренировка": 0,
        "история": 2,
    }.get(format_key, seed % len(LAYOUTS))
    renderer = LAYOUTS[(preferred + variant) % len(LAYOUTS)]
    image = renderer(lines, seed, scene, channel)
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def preview_variants(channel: str, post_text: str, format_key: str, count: int = 3) -> list[bytes]:
    return [render_card(channel, post_text, format_key, variant=index) for index in range(max(1, min(count, 3)))]
