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
    assert "⚡" in decorated and "🔥" in decorated
    assert "🧠" not in decorated and "⚽" not in decorated


def test_decorate_limits_emoji_and_drops_final_period():
    value="Хук. ⚽\n\nМысль 🔥.\n\nВывод 👀.\n\nЧто выберешь."
    decorated=decorate_post(value,"liga")
    assert decorated.count("⚡") + decorated.count("🔥") == 2
    assert ". ⚡" not in decorated and "🔥." not in decorated
    assert decorated.endswith("Что выберешь")

def test_custom_emoji_is_rendered_with_safe_numeric_id():
    result=telegram_html("⚡ Хук",{"⚡":"5368324170671202286"})
    assert '<tg-emoji emoji-id="5368324170671202286">⚡</tg-emoji>' in result

def test_custom_emoji_rejects_non_numeric_id():
    assert "tg-emoji" not in telegram_html("⚡ Хук",{"⚡":"bad"})

def test_custom_emoji_matches_with_or_without_variation_selector():
    result=telegram_html("⚠️ Риск и ⚠ риск",{"⚠":"5368324170671202286"})
    assert result.count("<tg-emoji") == 2
    assert "__CUSTOM_EMOJI" not in result
