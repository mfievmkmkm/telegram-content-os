from content_os.operator_runtime import operator_keyboard


def test_operator_home_is_product_first_and_compact():
    markup = operator_keyboard()
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert labels[:2] == ["● TODAY", "＋ CREATE"]
    assert "▶ STUDIO" in labels
    assert "↗ GROWTH" in labels
    assert "₽ SALES" in labels
    assert "◆ KNOWLEDGE" in labels
    assert "⚙ SYSTEM" in labels
    assert len(labels) == 9


def test_studio_distinguishes_empty_drafts_from_database_error():
    from types import SimpleNamespace
    from content_os.operator_runtime import _draft_picker
    empty = _draft_picker(SimpleNamespace(recent_drafts=lambda *args: []),"remixv2:start")
    assert empty.inline_keyboard[0][0].callback_data == "v2:create"
    def broken(*args): raise ConnectionError("database down")
    failed = _draft_picker(SimpleNamespace(recent_drafts=broken),"remixv2:start")
    assert failed.inline_keyboard[0][0].callback_data == "v2:remix"
    assert "БД недоступна" in failed.inline_keyboard[0][0].text
