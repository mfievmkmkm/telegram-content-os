from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .smoke_contract import SMOKE_STEPS


class RolloutStage(str, Enum):
    BLOCKED = "blocked"
    SAFE_SMOKE = "safe_smoke"
    PRIVATE_SMOKE = "private_smoke"
    CANARY = "canary"
    READY = "ready"


@dataclass(frozen=True)
class RolloutDecision:
    stage: RolloutStage
    allowed: tuple[str, ...]
    blocking: tuple[str, ...]
    note: str


def decide_rollout(*, env_ready: bool, completed: Iterable[str], ci_green: bool, auto_publish: bool) -> RolloutDecision:
    done = {str(x).strip() for x in completed}
    safe = {s.key for s in SMOKE_STEPS if not s.destructive}
    destructive = {s.key for s in SMOKE_STEPS if s.destructive}
    all_steps = {s.key for s in SMOKE_STEPS}
    blocking = []
    if not ci_green:
        blocking.append("CI must be green")
    if not env_ready:
        blocking.append("release gate must pass")
    if auto_publish:
        blocking.append("AUTO_PUBLISH must stay off during rollout")
    if blocking:
        return RolloutDecision(RolloutStage.BLOCKED, (), tuple(blocking), "Do not switch production runtime")
    if not safe.issubset(done):
        return RolloutDecision(RolloutStage.SAFE_SMOKE, tuple(sorted(safe - done)), (), "Run non-destructive checks first")
    if not destructive.issubset(done):
        return RolloutDecision(RolloutStage.PRIVATE_SMOKE, tuple(sorted(destructive - done)), (), "Only private/test destinations")
    if not all_steps.issubset(done):
        return RolloutDecision(RolloutStage.CANARY, tuple(sorted(all_steps - done)), (), "Keep rollback flag available")
    return RolloutDecision(RolloutStage.READY, (), (), "V2 may proceed to controlled canary; auto-publish remains a separate decision")
