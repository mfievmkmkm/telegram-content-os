from content_os.hooks import passes_hook_gate, score_hook


def test_boring_hook_fails():
    assert not passes_hook_gate("Всем привет! Сегодня мы поговорим про футбол.\nТекст")


def test_sharp_hook_passes():
    score, _ = score_hook("Твой тренер уже понял, что ты боишься мяча")
    assert score >= 3


def test_long_hook_loses_point():
    score, reasons = score_hook("Почему твой тренер уже давно видит каждую твою ошибку и никогда не говорит об этом прямо после матча потому что ждёт твоей реакции")
    assert score < 5
    assert reasons

