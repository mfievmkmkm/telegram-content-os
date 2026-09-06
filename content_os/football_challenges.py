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
    Challenge("half_turn", "Полуоборот до мяча", "field", 12, "Поставь ориентир за спиной. Перед передачей сканируй, принимай дальней ногой и первым касанием выходи в полуоборот.", "16 выходов в нужную сторону из 20", "Видео серии из 5 повторений"),
    Challenge("one_v_one_delay", "Не бросайся в отбор", "field", 14, "В 1v1 сначала сократи пространство, разверни соперника в неудобную сторону и только после тяжёлого касания вступай в отбор.", "7 выигранных эпизодов из 10 без фола", "Видео всех 10 эпизодов"),
    Challenge("finish_under_fatigue", "Удар после усталости", "field", 16, "Короткий интенсивный рывок, смена направления и удар вторым касанием. Не жертвуй постановкой корпуса ради силы.", "12 попаданий в целевую зону из 18", "Видео первых и последних 3 ударов"),
    Challenge("protect_and_exit", "Корпус под давлением", "field", 12, "Прими мяч спиной к давлению, закрой его дальней ногой и выйди через одну из двух ворот после контакта.", "15 сохранений мяча из 20", "Видео 5 попыток подряд"),
    Challenge("keeper_first_pass", "Вратарь начинает атаку", "goalkeeper", 15, "После ловли быстро оцени две цели и начни атаку рукой или низкой передачей в свободную сторону.", "8 точных решений из 10", "Видео серии с обеими целями"),
    Challenge("recovery_run", "Рывок после потери", "all", 12, "После условной потери мгновенно развернись, займи линию между мячом и воротами и только затем атакуй игрока.", "10 правильных возвратов подряд", "Видео последней серии"),
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
