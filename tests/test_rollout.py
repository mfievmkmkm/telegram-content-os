from content_os.rollout import RolloutStage, decide_rollout
from content_os.smoke_contract import SMOKE_STEPS


def test_rollout_blocks_on_ci_env_or_autopublish():
    assert decide_rollout(env_ready=False, completed=(), ci_green=True, auto_publish=False).stage == RolloutStage.BLOCKED
    assert decide_rollout(env_ready=True, completed=(), ci_green=False, auto_publish=False).stage == RolloutStage.BLOCKED
    assert decide_rollout(env_ready=True, completed=(), ci_green=True, auto_publish=True).stage == RolloutStage.BLOCKED


def test_rollout_starts_with_safe_checks():
    decision = decide_rollout(env_ready=True, completed=(), ci_green=True, auto_publish=False)
    assert decision.stage == RolloutStage.SAFE_SMOKE
    assert "publish_private" not in decision.allowed
    assert "sales" not in decision.allowed


def test_rollout_unlocks_private_actions_only_after_safe_phase():
    safe = [s.key for s in SMOKE_STEPS if not s.destructive]
    decision = decide_rollout(env_ready=True, completed=safe, ci_green=True, auto_publish=False)
    assert decision.stage == RolloutStage.PRIVATE_SMOKE
    assert set(decision.allowed) == {"publish_private", "sales"}


def test_complete_contract_is_ready_but_does_not_enable_autopublish():
    all_steps = [s.key for s in SMOKE_STEPS]
    decision = decide_rollout(env_ready=True, completed=all_steps, ci_green=True, auto_publish=False)
    assert decision.stage == RolloutStage.READY
    assert "auto-publish" in decision.note.lower()
