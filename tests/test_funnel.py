from content_os.funnel import summarize_funnel


def test_funnel_conversion_and_breakdowns():
    events=[
      {"event_type":"landing","source":"liga_post","offer_key":None},
      {"event_type":"landing","source":"liga_post","offer_key":None},
      {"event_type":"offer_view","source":"liga_post","offer_key":"liga_episode"},
      {"event_type":"order_created","source":"liga_post","offer_key":"liga_episode"},
    ]
    result=summarize_funnel(events)
    assert result["conversion"] == 50.0
    assert result["sources"]["liga_post"] == 2
    assert result["offers"]["liga_episode"] == 1
