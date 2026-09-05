from __future__ import annotations

from dataclasses import dataclass

from .core import alignment_chunks, caption_chunks


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


def ass_subtitles_v2(script: str, duration: float, preset: str = "punch", alignment: dict | None = None) -> str:
    style = subtitle_style(preset)
    timed = alignment_chunks(alignment or {}, max_words=style.max_words)
    chunks = caption_chunks(script, max_words=style.max_words)
    total = sum(len(x.split()) for x in chunks)
    cursor = 0.0
    lines = []

    def stamp(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int(seconds % 3600 // 60)
        rest = seconds % 60
        return f"{hours}:{minutes:02d}:{rest:05.2f}"

    entries = timed or [(chunk, None, None) for chunk in chunks]
    for chunk, aligned_start, aligned_end in entries:
        if aligned_start is None:
            share = max(.7, duration * len(chunk.split()) / max(1, total))
            start, end = cursor, min(duration, cursor + share)
        else:
            start = max(0.0, aligned_start - .04)
            end = min(duration, aligned_end + .08)
        words = chunk.replace("{", "(").replace("}", ")").replace("\n", " ").split()
        if style.accent_last_word and words:
            safe = " ".join(words[:-1] + [r"{\c&H55FFB0&}" + words[-1] + r"{\c&HFFFFFF&}"])
        else:
            safe = " ".join(words)
        lines.append(f"Dialogue: 0,{stamp(start)},{stamp(end)},Main,,0,0,0,,{safe}")
        cursor = end

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,DejaVu Sans,{style.font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H00000000,-1,0,0,0,100,100,0,0,1,{style.outline},{style.shadow},2,68,68,{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header + "\n".join(lines) + "\n"
