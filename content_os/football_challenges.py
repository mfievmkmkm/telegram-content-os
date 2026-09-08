from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib


@dataclass(frozen=True)
class Challenge:
    key: str
    title: str
    position: str
    duration_min: int
    task: str
    success_metric: str
    proof: str


LIBRARY = (
    Challenge("scan_before_receive", "Скан до приёма", "all", 12, "Перед каждым приёмом дважды посмотри через плечо и только потом открывай корпус.", "20 чистых повторений подряд", "Короткое видео 3–5 повторений"),
    Challenge("weak_foot_wall", "Слабая нога без отмазок", "field", 15, "Работай в стену только слабой: приём в сторону и передача в два касания.", "50 точных передач из 60", "Видео последней серии"),
    Challenge("first_touch_escape", "Первый приём из давления", "field", 15, "Поставь два конуса как ворота. Первый приём каждый раз должен выводить мяч через свободные ворота.", "16 удачных выходов из 20", "Видео 5 попыток подряд"),
    Challenge("keeper_set", "Вратарь: стойка до удара", "goalkeeper", 12, "Перед каждым броском или ударом успевай остановить ноги и занять готовую стойку.", "8 правильных установок из 10", "Видео серии из 10 действий"),
    Challenge("repeat_sprint", "Не сдохнуть после рывка", "all", 14, "6 серий: короткий рывок, быстрое восстановление, затем техническое действие с мячом.", "Техника не разваливается в последних двух сериях", "Видео первой и шестой серии"),
)


def _eligible(position: str) -> list[Challenge]:
    p = (position or "all").lower()
    result = [c for c in LIBRARY if c.position in {"all", p}]
    if p == "goalkeeper":
        result = [c for c in LIBRARY if c.position in {"all", "goalkeeper"}]
    elif p not in {"goalkeeper", "all"}:
        result = [c for c in LIBRARY if c.position in {"all", "field"}]
    return result or list(LIBRARY)


def daily_challenge(player_id: str | int, position: str = "all", day: date | None = None, recent_keys: tuple[str, ...] = ()) -> Challenge:
    """Stable daily selection with a recent-item exclusion window."""
    day = day or date.today()
    candidates = _eligible(position)
    fresh = [c for c in candidates if c.key not in set(recent_keys)] or candidates
    seed = f"{player_id}:{position}:{day.isoformat()}".encode("utf-8")
    index = int(hashlib.sha256(seed).hexdigest()[:8], 16) % len(fresh)
    return fresh[index]


def progress_score(completed: int, attempted: int) -> int:
    if attempted <= 0:
        return 0
    return max(0, min(100, round(completed / attempted * 100)))
