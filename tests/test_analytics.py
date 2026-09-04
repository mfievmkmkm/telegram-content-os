from types import SimpleNamespace

from content_os.analytics import reaction_count

def test_reactions_are_summed():
    message=SimpleNamespace(reactions=SimpleNamespace(results=[SimpleNamespace(count=3),SimpleNamespace(count=4)]))
    assert reaction_count(message)==7

def test_missing_reactions():
    assert reaction_count(SimpleNamespace(reactions=None))==0


def test_report_names_formats_to_scale():
    class Db:
        def analytics_summary(self):
            return [{"channel_key":"gifts","format_key":"мем","hook_score":5,"text":"Хук\nТекст","views":100,"reactions":8,"forwards":2,"engagement":12.0}]
        def editorial_insights(self,channel):
            return [{"format_key":"мем","avg_er":12.0,"samples":3}] if channel=="gifts" else []
    from content_os.analytics import AnalyticsCollector
    report=AnalyticsCollector(None,Db()).report()
    assert "Что масштабировать" in report and "мем — ER 12.00%" in report
