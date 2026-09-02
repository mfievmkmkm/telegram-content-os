from content_os.history import parse_preview, parse_views


def test_views():
    assert parse_views("1.2K")==1200
    assert parse_views("42")==42


def test_preview_parser():
    page='''<div class="tgme_widget_message" data-post="demo/77"><div class="tgme_widget_message_text">Хук<br>Текст</div><span class="tgme_widget_message_views">1.2K</span><time datetime="2026-09-02T10:00:00+00:00"></time></div>'''
    posts=parse_preview(page,"demo")
    assert posts[0]["id"]==77
    assert posts[0]["text"]=="Хук\nТекст"
    assert posts[0]["views"]==1200
