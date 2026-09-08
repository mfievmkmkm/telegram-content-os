from content_os.growth.decision import decide_experiment
from content_os.growth.experiments import Experiment, ExperimentVariant


def exp(samples=2):
    return Experiment("loss hook", "hook", ExperimentVariant("A", {"hook":"guide"}), ExperimentVariant("B", {"hook":"loss"}), "bot_starts", samples)


def test_decision_waits_for_samples():
    assert decide_experiment(exp(3), [1, 2], [2, 3]).status == "collecting"


def test_decision_reports_direction_without_significance_claim():
    result = decide_experiment(exp(), [10, 10], [13, 13])
    assert result.status == "challenger_leads"
    assert round(result.lift_percent) == 30
    assert "no significance claim" in result.reason


def test_small_difference_is_inconclusive():
    assert decide_experiment(exp(), [100, 100], [104, 104]).status == "inconclusive"
