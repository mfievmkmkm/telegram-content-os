from content_os.operator_runtime import operator_keyboard


def test_operator_home_is_product_first_and_compact():
    markup = operator_keyboard()
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert labels[:2] == ["⚡ TODAY", "✚ CREATE"]
    assert "🎬 STUDIO" in labels
    assert "📊 GROWTH" in labels
    assert "🛒 SALES" in labels
    assert "🧠 KNOWLEDGE" in labels
    assert "⚙️ SYSTEM" in labels
    assert len(labels) == 9
