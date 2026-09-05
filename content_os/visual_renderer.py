from __future__ import annotations

import hashlib
import io

from . import brand_cards
from .formatting import plain_text


def render_card(channel: str, post_text: str, format_key: str, variant: int = 0) -> bytes:
    """Render a stable visual alternative without changing the post text.

    The existing card engine remains the source of brand language. Variant only
    changes its deterministic seed, so three previews are reproducible and do not
    require another LLM call.
    """
    variant = max(0, min(int(variant), 8))
    lines = brand_cards._lines(post_text)
    salt = f"{channel}:{format_key}:variant:{variant}:{plain_text(post_text)}"
    seed = int(hashlib.sha256(salt.encode("utf-8")).hexdigest()[:8], 16)
    if channel == "gifts":
        scene = "fomo_meme.webp" if format_key == "мем" else brand_cards._pick_gift_scene(plain_text(post_text), seed)
    elif channel == "liga":
        scene = ("empty_bench.webp", "golden_bench.webp")[seed % 2] if format_key == "мем" else brand_cards._pick_liga_scene(plain_text(post_text), seed)
    else:
        raise ValueError(f"Unknown channel: {channel}")
    image = brand_cards._designed(lines, seed, scene, channel, format_key)
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def preview_variants(channel: str, post_text: str, format_key: str, count: int = 3) -> list[bytes]:
    return [render_card(channel, post_text, format_key, variant=index) for index in range(max(1, min(count, 3)))]
