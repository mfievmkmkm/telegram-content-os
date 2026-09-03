from content_os.articles import extract_article


def test_extract_article_ignores_navigation_and_keeps_story():
    page="""<html><head><title>Матч без мяча</title><meta name="description" content="Короткое описание материала"></head>
    <body><nav>Меню и реклама</nav><article><p>Игрок сделал рывок за спину защитнику и освободил коридор для передачи партнёра.</p>
    <p>Этот эпизод показывает, почему движение без мяча иногда важнее самого касания.</p></article></body></html>"""
    title,text=extract_article(page)
    assert title=="Матч без мяча"
    assert "рывок за спину" in text
    assert "Меню и реклама" not in text
