from __future__ import annotations

import re
from dataclasses import dataclass

from .content_fingerprint import ContentFingerprint, repetition_gate, signature
from .creative_director import DirectorReport, inspect_content
from .formatting import plain_text


HOOK_PATTERNS = {
    "question": re.compile(r"\?$"),
    "number": re.compile(r"\d"),
    "warning": re.compile(r"\b(ошиб|опас|потер|слил|провал|нельзя|не делай)\w*", re.I),
    "conflict": re.compile(r"\b(но|против|вместо|почему|на самом деле)\b", re.I),
}


def infer_hook_type(text: str) -> str:
    first = next((line.strip() for line in plain_text(text).splitlines() if line.strip()), "")
    for key, pattern in HOOK_PATTERNS.items():
        if pattern.search(first):
            return key
    return "statement"


def infer_emotion(text: str) -> str:
    value = plain_text(text).lower()
    if re.search(r"😂|мем|смеш|абсурд|орнул|кринж", value): return "meme"
    if re.search(r"ошиб|потер|опас|страх|слил|риск", value): return "tension"
    if re.search(r"побед|рост|прогресс|получ|смог", value): return "upside"
    return "neutral"


def infer_cta(text: str) -> str:
    tail = " ".join(plain_text(text).lower().split()[-30:])
    if re.search(r"бот|подпис|зайди|открой|проверь", tail): return "conversion"
    if "?" in tail: return "discussion"
    if re.search(r"сохрани|перешли|отправь", tail): return "share"
    return "none"


def build_fingerprint(*, text: str, topic: str, angle: str, format_key: str, visual_type: str = "") -> ContentFingerprint:
    return ContentFingerprint(
        topic=(topic or "unknown").strip().lower()[:120],
        angle=(angle or "unknown").strip().lower()[:120],
        hook_type=infer_hook_type(text),
        format_key=format_key,
        emotion=infer_emotion(text),
        cta_type=infer_cta(text),
        visual_type=visual_type,
        text_signature=signature(text),
    )


@dataclass(slots=True)
class QualityDecision:
    approved: bool
    fingerprint: ContentFingerprint
    report: DirectorReport
    similarity: float
    repetition_reason: str = ""


def review_candidate(
    *,
    text: str,
    channel: str,
    topic: str,
    angle: str,
    format_key: str,
    history: list[tuple[ContentFingerprint, str]] | None = None,
    visual_type: str = "",
) -> QualityDecision:
    fp = build_fingerprint(text=text, topic=topic, angle=angle, format_key=format_key, visual_type=visual_type)
    repeat = repetition_gate(fp, text, history or [])
    report = inspect_content(text, channel=channel, similarity_score=repeat.score if not repeat.allowed else 0.0)
    return QualityDecision(
        approved=report.approved and repeat.allowed,
        fingerprint=fp,
        report=report,
        similarity=repeat.score,
        repetition_reason=repeat.reason,
    )
