from content_os.growth.scorecard import rank_content, score_content


def test_score_rewards_downstream_action_more_than_vanity_reaction():
    vanity = score_content({"content_id":"a","views":1000,"reactions":100})
    buyer = score_content({"content_id":"b","views":1000,"reactions":10,"clicks":20,"leads":10,"orders":5,"sales":2,"revenue":100})
    assert buyer.total > vanity.total
    assert buyer.revenue == 100


def test_low_sample_content_is_excluded_from_default_ranking():
    rows=[{"content_id":"viral-small","views":20,"reactions":20},{"content_id":"real","views":500,"reactions":20,"clicks":10}]
    ranked=rank_content(rows)
    assert [item.content_id for item in ranked] == ["real"]


def test_zero_views_is_safe():
    item=score_content({"content_id":"x","sales":1})
    assert item.total == 0
