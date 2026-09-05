from content_os.content_doctor import diagnose, render


def test_empty_doctor_report_is_safe():
    report = diagnose("")
    assert report.score == 0
    assert len(report.metrics) == 6


def test_actionable_copy_beats_vague_copy():
    vague = diagnose("В современном мире важно понимать роль контента.")
    strong = diagnose(
        "Почему твой Telegram-пост умирает в первой строке?\n\n"
        "Покажу разбор на реальном примере: где теряется внимание и что переписать.\n\n"
        "Пришли свой пост — разберу хук и CTA."
    )
    assert strong.score > vague.score
    assert next(x for x in strong.metrics if x.key == "hook").score >= 70
    assert next(x for x in strong.metrics if x.key == "cta").score >= 70


def test_render_contains_scorecard():
    text = render(diagnose("Как перестать сливать внимание в первом экране? Пришли пост — покажу разбор."))
    assert "CONTENT DOCTOR" in text
    assert "HOOK" in text
    assert "CTA" in text
