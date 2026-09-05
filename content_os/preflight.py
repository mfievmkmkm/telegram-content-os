from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .release_gate import evaluate_release, evaluate_shorts_worker
from .rollout import RolloutDecision, decide_rollout
from .system_health import SubsystemStatus, subsystem_statuses


@dataclass(frozen=True)
class PreflightReport:
    editor_ready: bool
    worker_ready: bool
    subsystems: tuple[SubsystemStatus, ...]
    rollout: RolloutDecision
    blocking: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready_for_live_smoke(self) -> bool:
        return self.editor_ready and self.worker_ready and not self.blocking


def build_preflight(
    editor_env: Mapping[str, str],
    worker_env: Mapping[str, str],
    *,
    completed_smoke: Iterable[str] = (),
    ci_green: bool = False,
) -> PreflightReport:
    """Build one deploy-safe report without exposing any secret values."""
    editor = evaluate_release(editor_env, require_shorts=True)
    worker = evaluate_shorts_worker(worker_env)
    statuses = subsystem_statuses({**dict(editor_env), **dict(worker_env)})
    blocking = list(editor.blocking) + list(worker.blocking)
    rollout = decide_rollout(
        env_ready=editor.ready and worker.ready,
        completed=completed_smoke,
        ci_green=ci_green,
        auto_publish=str(editor_env.get("AUTO_PUBLISH", "false")).lower() in {"1", "true", "yes"},
    )
    blocking.extend(rollout.blocking)
    warnings = tuple(dict.fromkeys((*editor.warnings, *worker.warnings)))
    return PreflightReport(
        editor_ready=editor.ready,
        worker_ready=worker.ready,
        subsystems=statuses,
        rollout=rollout,
        blocking=tuple(dict.fromkeys(blocking)),
        warnings=warnings,
    )


def missing_variable_names(report: PreflightReport) -> tuple[str, ...]:
    """Return names only, never values, for operator-facing setup instructions."""
    names=[]
    for item in report.blocking:
        if item.startswith("missing:"):
            names.append(item.split(":",1)[1])
    return tuple(dict.fromkeys(names))
