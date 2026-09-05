from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubtitleStyle:
    key: str
    font_size: int
    margin_v: int
    outline: int
    shadow: int
    max_words: int
    accent_last_word: bool


STYLES = {
    "punch": SubtitleStyle("punch", 62, 235, 4, 2, 2, True),
    "clean": SubtitleStyle("clean", 54, 210, 3, 1, 3, False),
    "sport": SubtitleStyle("sport", 60, 250, 4, 1, 2, True),
    "meme": SubtitleStyle("meme", 66, 205, 5, 2, 2, True),
}


def subtitle_style(key: str) -> SubtitleStyle:
    return STYLES.get((key or "punch").strip().lower(), STYLES["punch"])
