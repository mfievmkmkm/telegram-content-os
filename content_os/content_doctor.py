from __future__ import annotations

import re
from dataclasses import dataclass

from .formatting import plain_text


@dataclass(frozen=True, slots=True)
class DoctorMetric:
    key: str
    label: str
    score: int
    note: str


@dataclass(frozen=True, slots=True)
class DoctorReport:
    score: int
    metrics: tuple[DoctorMetric, ...]
    problems: tuple[str, ...]
    next_action: str


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def diagnose(text: str) -> DoctorReport:
    """Fast deterministic audit for Telegram/social copy.

    This deliberately does not invent facts or claim predicted reach. Scores are
    editorial heuristics that make the rewrite workflow explainable and testable.
    """
    clean = plain_text(text or "").strip()
    if not clean:
        metrics = tuple(DoctorMetric(k, label, 0, "Нет текста для оценки") for k, label in (
            ("hook", "HOOK"), ("clarity", "CLARITY"), ("emotion", "EMOTION"),
            ("trust", "TRUST"), ("cta", "CTA"), ("offer", "OFFER"),
        ))
        return DoctorReport(0, metrics, ("Пришли текст поста, оффера или сценария",), "Добавить исходник")

    words = clean.split()
    first = _first_line(clean)
    lower = clean.lower()

    hook = 48
    if 3 <= len(first.split()) <= 12: hook += 24
    if re.search(r"[?!]|\d|\b(почему|как|ошиб|нельзя|если|вместо|слил|потер)\w*", first, re.I): hook += 18
    if len(first) > 125: hook -= 28
    if first.endswith(".") and len(first.split()) > 12: hook -= 12

    clarity = 76
    if len(words) > 420: clarity -= 24
    if len(words) < 18: clarity -= 14
    long_sentences = [x for x in re.split(r"[.!?\n]+", clean) if len(x.split()) > 28]
    clarity -= min(28, len(long_sentences) * 7)
    if "\n" in clean: clarity += 6

    emotion = 38
    emotion += min(32, len(re.findall(r"\b(боль|страх|риск|потер|слил|бесит|хочешь|получ|рост|выиг|кринж|мем|абсурд)\w*", lower)) * 7)
    if re.search(r"[!?]", clean): emotion += 8

    trust = 66
    if re.search(r"\b(пример|покаж|разбор|кейс|результат|данн|источник|скрин|факт)\w*", lower): trust += 18
    numeric = bool(re.search(r"\d+[.,]?\d*\s?(?:%|ton|₽|\$|€)", lower))
    if numeric and not re.search(r"\b(по данным|источник|скрин|факт|результат|мой|наши)\b", lower): trust -= 12
    if re.search(r"\b(гарантир|100%|без риска|точно заработ)\w*", lower): trust -= 25

    cta = 28
    if re.search(r"\b(напиши|жми|открой|зайди|подпиш|сохрани|отправь|пришли|закаж|проверь|скачай)\w*", lower): cta += 52
    if clean.rstrip().endswith("?"): cta += 10

    offer = 34
    if re.search(r"\b(получишь|результат|сделаю|разбер|упак|создам|готов|под ключ|за \d|₽|\$)\w*", lower): offer += 34
    if re.search(r"\b(за \d+|дн|час|срок|сегодня|завтра)\w*", lower): offer += 12
    if re.search(r"\b(для кого|кому|если ты|тебе)\b", lower): offer += 10

    values = {
        "hook": _clamp(hook), "clarity": _clamp(clarity), "emotion": _clamp(emotion),
        "trust": _clamp(trust), "cta": _clamp(cta), "offer": _clamp(offer),
    }
    notes = {
        "hook": "Останавливает ли первая строка скролл",
        "clarity": "Насколько быстро считывается мысль",
        "emotion": "Есть ли напряжение, желание или реакция",
        "trust": "Есть ли основания верить обещаниям и цифрам",
        "cta": "Понятно ли, что делать после текста",
        "offer": "Понятны ли результат, ценность и конкретика",
    }
    labels = {"hook":"HOOK","clarity":"CLARITY","emotion":"EMOTION","trust":"TRUST","cta":"CTA","offer":"OFFER"}
    metrics = tuple(DoctorMetric(k, labels[k], values[k], notes[k]) for k in labels)
    score = round(sum(values.values()) / len(values))
    weakest = sorted(metrics, key=lambda item: item.score)[:3]
    problems = tuple(f"{item.label}: {item.note.lower()} — {item.score}/100" for item in weakest)
    next_action = "Переписать хук" if weakest[0].key == "hook" else "Пересобрать слабые блоки"
    return DoctorReport(score, metrics, problems, next_action)


def render(report: DoctorReport) -> str:
    lines = [f"🧠 <b>CONTENT DOCTOR · {report.score}/100</b>", ""]
    for item in report.metrics:
        bar = "█" * max(1, round(item.score / 20)) + "░" * max(0, 5 - round(item.score / 20))
        lines.append(f"<b>{item.label:<8}</b> {bar} {item.score}")
    lines.extend(["", "<b>Что режет результат:</b>"])
    lines.extend(f"• {problem}" for problem in report.problems)
    lines.extend(["", f"→ {report.next_action}"])
    return "\n".join(lines)
