from content_os.sales.pipeline import actions_for_order, retention_suggestion


def test_new_order_can_move_to_qualified_only():
    actions=actions_for_order({"id":1,"status":"new"})
    assert [item.target_status for item in actions] == ["qualified"]


def test_old_accepted_status_maps_into_v2_lifecycle():
    actions=actions_for_order({"id":2,"status":"accepted"})
    assert any(item.target_status == "quoted" for item in actions)


def test_paid_transition_marks_sale_event():
    actions=actions_for_order({"id":3,"status":"awaiting_payment"})
    paid=next(item for item in actions if item.target_status == "paid")
    assert paid.event_type == "sale"


def test_retention_only_after_delivery():
    assert retention_suggestion({"status":"in_progress","offer_key":"ai_short"}) is None
    suggestion=retention_suggestion({"status":"delivered","offer_key":"ai_short"})
    assert suggestion is not None
    assert suggestion.kind == "repeat"
