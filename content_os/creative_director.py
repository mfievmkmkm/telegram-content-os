from __future__ import annotations

import re
from dataclasses import dataclass, field

from .formatting import plain_text


@dataclass(frozen=True)
class DirectorIssue:
    code: str
    message: str
    severity: str = "warning"
    penalty: int = 0


@dataclass
class DirectorReport:
    score: int = 100
    issues: list[DirectorIssue] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return self.score >= 72 and not any(x.severity == "block" for x in self.issues)

    def add(self, issue: DirectorIssue) -> None:
        self.issues.append(issue)
        self.score = max(0, self.score - issue.penalty)


def inspect_content(text: str, *, channel: str, similarity_score: float = 0.0) -> DirectorReport:
    report = DirectorReport()
    clean = plain_text(text or "").strip()
    words = clean.split()
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    first = lines[0] if lines else ""

    if len(words) < 35:
        report.add(DirectorIssue("too_short", "Материал слишком короткий: мысль не успевает раскрыться", penalty=12))
    if len(words) > 420:
        report.add(DirectorIssue("too_long", "Материал перегружен: нужен более жёсткий монтаж текста", penalty=10))
    if len(first) > 125:
        report.add(DirectorIssue("weak_hook_shape", "Первая строка слишком длинная для сильного хука", penalty=10))
    if first and first[-1:] == "." and len(first.split()) > 14:
        report.add(DirectorIssue("slow_hook", "Хук похож на вводный абзац, а не на остановку скролла", penalty=8))

    emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF]", clean))
    if emoji_count > 3:
        report.add(DirectorIssue("emoji_overload", f"Эмодзи перегружают материал: {emoji_count}, лимит — 3", penalty=min(14, emoji_count - 3)))

    if similarity_score >= .82:
        report.add(DirectorIssue("duplicate", "Материал почти повторяет недавнюю публикацию", "block", 35))
    elif similarity_score >= .70:
        report.add(DirectorIssue("similar", "Слишком знакомая тема/подача — нужен другой угол", "block", 24))

    numeric_claims = re.findall(r"(?<!\w)(?:\d+[.,]?\d*\s?(?:%|TON|₽|\$|€)|\+\d+%)(?!\w)", clean, re.I)
    if channel == "gifts" and numeric_claims:
        report.add(DirectorIssue("facts_required", "В Gifts есть цифры: перед публикацией нужен подтверждённый fact pack", "warning", 0))

    stale_phrases = (
        "рынок демонстрирует активность",
        "в современном мире",
        "важно понимать",
        "стоит отметить",
        "не финансовая рекомендация",
    )
    if any(phrase in clean.lower() for phrase in stale_phrases):
        # This is a brand-level rule, not a cosmetic warning. Content OS should
        # never show the admin the exact sterile phrases it was built to eliminate.
        report.add(DirectorIssue("sterile_phrase", "Нашёл стерильную/шаблонную формулировку", "block", 18))

    return report


def render_report(report: DirectorReport) -> str:
    icon = "✅" if report.approved else "🛑"
    lines = [f"{icon} CREATIVE DIRECTOR · {report.score}/100"]
    if not report.issues:
        lines.append("Материал прошёл базовый quality gate")
    else:
        for issue in report.issues:
            mark = "❌" if issue.severity == "block" else "•"
            lines.append(f"{mark} {issue.message}")
    return "\n".join(lines)
