from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .lifecycle import ORDER_STATES, can_transition


@dataclass(frozen=True)
class SalesAction:
    order_id: int | str
    action: str
    target_status: str
    label: str
    event_type: str = ""


@dataclass(frozen=True)
class RetentionSuggestion:
    kind: str
    label: str
    reason: str


_LABELS = {
    "qualified": "Уточнить задачу",
    "quoted": "Собрать предложение",
    "awaiting_payment": "Отправить оплату",
    "paid": "Оплата подтверждена",
    "in_progress": "Начать работу",
    "review": "Отправить на проверку",
    "delivered": "Выдать результат",
    "closed": "Закрыть заказ",
}


def actions_for_order(order: Mapping) -> tuple[SalesAction, ...]:
    status = str(order.get("status") or "new")
    order_id = order.get("id") or "?"
    if status not in ORDER_STATES:
        # rollout compatibility with old runtime statuses
        status = {"accepted": "qualified", "done": "closed"}.get(status, "new")
    result = []
    for target, label in _LABELS.items():
        if can_transition(status, target):
            event = "sale" if target == "paid" else ""
            result.append(SalesAction(order_id, target, target, label, event))
    return tuple(result)


def retention_suggestion(order: Mapping) -> RetentionSuggestion | None:
    """Suggest the next useful outcome only after delivery/closure; no spam automation."""
    status = str(order.get("status") or "")
    if status not in {"delivered", "closed", "done"}:
        return None
    offer = str(order.get("offer_key") or "")
    if offer in {"liga_episode", "episode_review"}:
        return RetentionSuggestion("upsell", "Полный Player Development Pack", "После разбора одного эпизода логичный следующий шаг — план работы, а не ещё один случайный разбор")
    if offer in {"ai_short", "shorts_pack"}:
        return RetentionSuggestion("repeat", "Shorts Pack", "После первого ролика можно масштабировать только если клиенту подошёл результат")
    if offer in {"tg_pack", "content_system"}:
        return RetentionSuggestion("followup", "Проверить результат через 7 дней", "Сначала измеряем эффект внедрения, затем предлагаем следующий шаг")
    return RetentionSuggestion("followup", "Спросить, что изменилось после результата", "Повторная продажа начинается с результата клиента, а не с автоматического оффера")
