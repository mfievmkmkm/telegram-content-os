import pytest

from content_os.sales import DiagnosticInput, recommend
from content_os.sales.lifecycle import OrderTransition, can_transition, validate_transition


def test_diagnostic_routes_gifts_to_subscription_product():
    result = recommend(DiagnosticInput(goal="Хочу сигналы и разборы по Telegram Gifts"))
    assert result.package.key == "gifts_intelligence"
    assert result.confidence >= 90


def test_diagnostic_does_not_oversell_one_football_episode():
    result = recommend(DiagnosticInput(goal="Футбол: хочу разобрать один момент, где потерял мяч", asset="video.mp4"))
    assert result.package.key == "football_episode"
    assert not result.missing


def test_diagnostic_routes_manual_process_to_system():
    result = recommend(DiagnosticInput(goal="Надо автоматизировать Telegram: бот, автопост и контент-процесс", channel="@example"))
    assert result.package.key == "content_os_setup"


def test_broad_content_request_starts_with_free_diagnosis():
    result = recommend(DiagnosticInput(goal="Контент слабый, посты не цепляют", notes="есть несколько старых постов"))
    assert result.package.key == "content_doctor"
    assert result.package.tier == "free"


def test_order_lifecycle_prevents_skipping_payment():
    assert can_transition("new", "qualified")
    assert not can_transition("quoted", "paid")
    assert can_transition("awaiting_payment", "paid")


def test_cancellation_requires_reason():
    with pytest.raises(ValueError, match="requires a note"):
        validate_transition(OrderTransition("new", "cancelled"))
    validate_transition(OrderTransition("new", "cancelled", note="клиент передумал"))
