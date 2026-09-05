from content_os.growth.experiment_results import evaluate
from content_os.growth.experiments import Experiment, ExperimentVariant


def experiment(samples=3):
    return Experiment(
        hypothesis="conflict hook improves engagement",
        primary_variable="hook",
        control=ExperimentVariant("A", {"hook":"question","format":"post"}),
        challenger=ExperimentVariant("B", {"hook":"conflict","format":"post"}),
        success_metric="engagement_rate",
        minimum_samples=samples,
    )


def test_does_not_pick_winner_before_sample_floor():
    result=evaluate(experiment(3), [.1,.11], [.2,.19])
    assert result.status == "collecting"


def test_winner_is_explicitly_provisional():
    result=evaluate(experiment(), [.10,.11,.09], [.15,.16,.14])
    assert result.status == "provisional_challenger"
    assert "повторить" in result.recommendation.lower()


def test_small_difference_is_inconclusive():
    result=evaluate(experiment(), [.10,.10,.10], [.105,.104,.106])
    assert result.status == "inconclusive"
