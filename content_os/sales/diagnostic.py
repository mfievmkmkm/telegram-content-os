from __future__ import annotations

from dataclasses import dataclass, field

from .catalog import SalesPackage, package


@dataclass(frozen=True)
class DiagnosticInput:
    goal: str
    vertical: str = ""
    channel: str = ""
    asset: str = ""
    urgency: str = ""
    budget: str = ""
    notes: str = ""

    @property
    def normalized(self) -> str:
        return " ".join((self.goal, self.vertical, self.channel, self.asset, self.notes)).lower().strip()


@dataclass(frozen=True)
class Recommendation:
    package: SalesPackage
    reason: str
    confidence: int
    missing: tuple[str, ...] = field(default_factory=tuple)


def _contains(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def recommend(data: DiagnosticInput) -> Recommendation:
    """Recommend a product from explicit intent before asking an LLM to decorate it.

    This layer is intentionally deterministic: the system should never route a
    footballer into an AI service or invent a paid package because generation was
    creative that day.
    """
    text = data.normalized

    if _contains(text, ("gift", "gifts", "гифт", "подар", "nft", "ton")) or data.vertical.lower() == "gifts":
        return Recommendation(package("gifts_intelligence"), "Задача относится к Gifts — это отдельный подписочный продукт", 98)

    football = data.vertical.lower() in {"football", "liga", "футбол"} or _contains(
        text, ("футбол", "матч", "эпизод", "позици", "вингер", "напада", "защитник", "вратар", "прессинг")
    )
    if football:
        if _contains(text, ("один эпизод", "один момент", "момент", "коротк", "ошибка в эпизоде")):
            return Recommendation(package("football_episode"), "Есть конкретный эпизод — начинать с большого пакета не нужно", 94, (() if data.asset else ("видео или ссылка на эпизод",)))
        return Recommendation(package("player_development"), "Нужна не разовая оценка, а системное улучшение игрока", 90, (() if data.asset else ("нарезка или несколько эпизодов",)))

    if _contains(text, ("автомат", "бот", "контент систем", "автопост", "процесс", "pipeline")):
        return Recommendation(package("content_os_setup"), "Проблема в ручном процессе, а не в одном материале", 94, (() if data.channel else ("площадка/канал",)))

    if _contains(text, ("telegram", "телеграм", "канал", "упаков", "ворон", "подписчик", "продаж")):
        return Recommendation(package("telegram_growth"), "Нужна упаковка канала и путь от контента к действию", 91, (() if data.channel else ("ссылка или описание канала",)))

    if _contains(text, ("short", "reels", "рилс", "ролик", "видео", "тикток", "tiktok", "озвуч")):
        return Recommendation(package("shorts_pack"), "Задача про регулярный вертикальный видеоконтент", 92, (() if data.asset else ("исходник, тема или пример",)))

    if _contains(text, ("пост", "текст", "контент", "оффер", "cta", "хук", "креатив")):
        return Recommendation(package("content_doctor"), "Сначала выгоднее бесплатно диагностировать материал, а потом продавать только нужное исправление", 86, (() if data.asset or data.notes else ("текст или материал для проверки",)))

    return Recommendation(
        package("content_doctor"),
        "Запрос пока слишком широкий — начинаем с диагностики, а не продаём пакет вслепую",
        62,
        ("что должно измениться после нашей работы",),
    )
