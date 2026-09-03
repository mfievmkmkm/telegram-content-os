from content_os.formatting import clean_generated_post, decorate_post, telegram_html


def test_sources_are_hidden_and_formatting_is_kept():
    value="🔥 **Хук**\n\n*Мысль*\n\nИсточник: https://example.com/x"
    assert "Источник" not in clean_generated_post(value)
    rendered=telegram_html(value)
    assert "<b>Хук</b>" in rendered
    assert "<i>Мысль</i>" in rendered
    assert "example.com" not in rendered


def test_untrusted_html_is_escaped():
    rendered=telegram_html("<script>x</script> <b>да</b>")
    assert "&lt;script&gt;" in rendered
    assert "<b>да</b>" in rendered


def test_decorate_guarantees_emphasis_and_emojis():
    value="Первый хук\n\nОсновная мысль\n\nПрактический вывод\n\nЧто выберешь?"
    decorated=decorate_post(value,"liga")
    assert decorated.count("<b>")==1
    assert decorated.count("<i>")==1
    assert "⚡" in decorated and "🧠" in decorated and "⚽" in decorated
