from __future__ import annotations

from dataclasses import dataclass


ORDER_STATES = (
    "new",
    "qualified",
    "quoted",
    "awaiting_payment",
    "paid",
    "in_progress",
    "review",
    "delivered",
    "closed",
    "cancelled",
)

_ALLOWED: dict[str, set[str]] = {
    "new": {"qualified", "cancelled"},
    "qualified": {"quoted", "cancelled"},
    "quoted": {"awaiting_payment", "qualified", "cancelled"},
    "awaiting_payment": {"paid", "quoted", "cancelled"},
    "paid": {"in_progress", "cancelled"},
    "in_progress": {"review", "cancelled"},
    "review": {"in_progress", "delivered"},
    "delivered": {"review", "closed"},
    "closed": set(),
    "cancelled": set(),
}


@dataclass(frozen=True)
class OrderTransition:
    current: str
    target: str
    actor: str = "system"
    note: str = ""


def can_transition(current: str, target: str) -> bool:
    if current not in _ALLOWED or target not in ORDER_STATES:
        return False
    return target in _ALLOWED[current]


def validate_transition(transition: OrderTransition) -> None:
    if not can_transition(transition.current, transition.target):
        raise ValueError(f"invalid order transition: {transition.current} -> {transition.target}")
    if transition.target == "cancelled" and not transition.note.strip():
        raise ValueError("cancellation requires a note")


def next_actions(status: str) -> tuple[str, ...]:
    labels = {
        "qualified": "Уточнить задачу",
        "quoted": "Согласовать предложение",
        "awaiting_payment": "Отправить оплату",
        "paid": "Подтвердить оплату",
        "in_progress": "Начать работу",
        "review": "Отправить на проверку",
        "delivered": "Выдать результат",
        "closed": "Закрыть заказ",
        "cancelled": "Отменить",
    }
    return tuple(labels[target] for target in _ALLOWED.get(status, set()) if target in labels)
