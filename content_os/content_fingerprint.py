from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from typing import Iterable

from .formatting import plain_text


@dataclass(frozen=True)
class ContentFingerprint:
    topic: str
    angle: str
    hook_type: str
    format_key: str
    emotion: str
    cta_type: str
    visual_type: str = ""
    text_signature: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_text(value: str) -> str:
    text = plain_text(value or "").lower().replace("ё", "е")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-zа-я0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def signature(value: str) -> str:
    return hashlib.sha1(normalize_text(value).encode("utf-8")).hexdigest()[:16]


def lexical_similarity(left: str, right: str) -> float:
    a, b = normalize_text(left), normalize_text(right)
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    aw, bw = set(a.split()), set(b.split())
    jaccard = len(aw & bw) / max(1, len(aw | bw))
    return round(max(seq, jaccard), 4)


def fingerprint_similarity(left: ContentFingerprint, right: ContentFingerprint) -> float:
    weighted = (
        (left.topic == right.topic, .30),
        (left.angle == right.angle, .25),
        (left.hook_type == right.hook_type, .15),
        (left.format_key == right.format_key, .10),
        (left.emotion == right.emotion, .08),
        (left.cta_type == right.cta_type, .07),
        (bool(left.visual_type) and left.visual_type == right.visual_type, .05),
    )
    return round(sum(weight for same, weight in weighted if same), 4)


@dataclass(frozen=True)
class RepetitionDecision:
    allowed: bool
    score: float
    reason: str = ""


def repetition_gate(
    candidate: ContentFingerprint,
    candidate_text: str,
    history: Iterable[tuple[ContentFingerprint, str]],
    *,
    semantic_threshold: float = .70,
    lexical_threshold: float = .72,
) -> RepetitionDecision:
    worst_score = 0.0
    worst_reason = ""
    for old_fp, old_text in history:
        fp_score = fingerprint_similarity(candidate, old_fp)
        text_score = lexical_similarity(candidate_text, old_text)
        score = max(fp_score, text_score)
        if score > worst_score:
            worst_score = score
            if text_score >= lexical_threshold:
                worst_reason = "Текст слишком похож на недавнюю публикацию"
            elif fp_score >= semantic_threshold:
                worst_reason = "Повторяется тема, угол или механика недавнего материала"
        if text_score >= lexical_threshold or fp_score >= semantic_threshold:
            return RepetitionDecision(False, score, worst_reason)
    return RepetitionDecision(True, worst_score, "")
