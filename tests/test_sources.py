from datetime import datetime, timedelta, timezone

from content_os.sources import clean_markup, score_item


def item(title, age, trust=3):
    return {"title":title,"summary":"football player training practical drill","trust":trust,"kind":"training",
            "published_at":datetime.now(timezone.utc)-timedelta(hours=age)}


def test_fresh_authoritative_item_wins():
    assert score_item(item("Why players make this mistake",2,5),"liga") > score_item(item("Old football note",240,2),"liga")


def test_markup_is_removed():
    assert clean_markup("<b>Хук</b> &amp; текст")=="Хук & текст"
