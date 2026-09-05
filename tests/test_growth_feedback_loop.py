from content_os.growth.feedback_loop import build_feedback_experiments


def _rows(n=6):
    rows=[]
    for _ in range(n):
        rows.append({"project":"gifts","hook_type":"conflict","format":"post","visual_type":"card","publish_hour":"17","offer":"access","engagement_rate":.20,"conversion_rate":.05})
        rows.append({"project":"gifts","hook_type":"question","format":"meme","visual_type":"meme","publish_hour":"11","offer":"none","engagement_rate":.08,"conversion_rate":.01})
    return rows


def test_feedback_builds_one_variable_experiments_only():
    result = build_feedback_experiments(
        _rows(6),
        "gifts",
        baseline={"hook":"question","format":"meme","visual":"meme","time":"11","offer":"none"},
    )
    assert result
    for item in result:
        control = item.experiment.control.values
        challenger = item.experiment.challenger.values
        changed = {key for key in set(control)|set(challenger) if control.get(key) != challenger.get(key)}
        assert changed == {item.experiment.primary_variable}


def test_feedback_respects_sample_floor():
    result = build_feedback_experiments(_rows(2), "gifts", baseline={"hook":"question"})
    assert result == ()


def test_feedback_never_proposes_noop_variant():
    result = build_feedback_experiments(_rows(6), "gifts", baseline={"hook":"conflict"})
    assert all(item.experiment.primary_variable != "hook" for item in result)
