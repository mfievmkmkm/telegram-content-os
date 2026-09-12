from content_os.editor import Editor
from content_os.hooks import score_hook


def test_plan_draft_gets_topic_aware_hook_instead_of_being_discarded():
    original="Обычная первая строка.\n\nПолезный и фактически безопасный разбор темы остаётся без изменений."
    rescued=Editor.rescue_hook(original,"психология статуса: желание показать покупку","gifts")
    assert "желание показать покупку" in rescued.splitlines()[0]
    assert score_hook(rescued)[0] >= 3
    assert "Полезный и фактически безопасный" in rescued
