from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SalesPackage:
    key: str
    vertical: str
    tier: str
    title: str
    promise: str
    deliverables: tuple[str, ...]
    price_label: str
    turnaround: str
    legacy_offer_keys: tuple[str, ...] = ()
    recurring: bool = False


PACKAGES: dict[str, SalesPackage] = {
    "content_doctor": SalesPackage(
        key="content_doctor",
        vertical="ai",
        tier="free",
        title="Content Doctor",
        promise="Покажет, где материал теряет внимание и что исправить первым",
        deliverables=("content score", "3 главные проблемы", "следующий шаг"),
        price_label="бесплатно",
        turnaround="сразу",
    ),
    "football_episode": SalesPackage(
        key="football_episode",
        vertical="football",
        tier="entry",
        title="Episode Review",
        promise="Разобрать одно конкретное игровое решение без общих оценок",
        deliverables=("размеченный эпизод", "3 конкретные правки", "лучший следующий ход"),
        price_label="390 ₽",
        turnaround="до 24 часов",
        legacy_offer_keys=("liga_episode",),
    ),
    "player_development": SalesPackage(
        key="player_development",
        vertical="football",
        tier="core",
        title="Player Development Pack",
        promise="Понять повторяющиеся игровые ошибки и получить понятный план улучшения",
        deliverables=("разбор эпизодов/нарезки", "Player Passport", "14-дневный план", "контрольные точки"),
        price_label="от 1 990 ₽",
        turnaround="2–4 дня",
        legacy_offer_keys=("liga_match", "liga_plan", "liga_passport"),
    ),
    "shorts_pack": SalesPackage(
        key="shorts_pack",
        vertical="ai",
        tier="core",
        title="Shorts Pack",
        promise="Получить серию вертикальных роликов, а не один случайный AI-монтаж",
        deliverables=("хуки и сценарии", "озвучка", "монтаж", "субтитры", "CTA"),
        price_label="от 2 490 ₽",
        turnaround="2–4 дня",
        legacy_offer_keys=("ai_short",),
    ),
    "telegram_growth": SalesPackage(
        key="telegram_growth",
        vertical="ai",
        tier="core",
        title="Telegram Growth Pack",
        promise="Упаковать канал так, чтобы контент вёл человека к следующему действию",
        deliverables=("позиционирование", "контент-матрица", "5 стартовых постов", "CTA и воронка"),
        price_label="от 2 990 ₽",
        turnaround="2–4 дня",
        legacy_offer_keys=("tg_pack",),
    ),
    "content_os_setup": SalesPackage(
        key="content_os_setup",
        vertical="ai",
        tier="system",
        title="Content OS Setup",
        promise="Собрать рабочий контент-процесс под Telegram вместо набора ручных действий",
        deliverables=("контент-бот", "редакторский workflow", "расписание", "публикация", "инструкция"),
        price_label="от 6 990 ₽",
        turnaround="от 5 дней",
        legacy_offer_keys=("content_system",),
    ),
    "gifts_intelligence": SalesPackage(
        key="gifts_intelligence",
        vertical="gifts",
        tier="recurring",
        title="Gifts Intelligence",
        promise="Получить доступ к отдельному продукту Gifts вместо покупки разовой услуги",
        deliverables=("подписка", "сигналы", "рыночные разборы", "закрытый доступ"),
        price_label="по тарифу подписки",
        turnaround="после активации",
        recurring=True,
    ),
}


def package(key: str) -> SalesPackage:
    try:
        return PACKAGES[key]
    except KeyError as exc:
        raise KeyError(f"Unknown sales package: {key}") from exc
