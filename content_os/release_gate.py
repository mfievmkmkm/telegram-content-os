from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class GateResult:
    ready: bool
    blocking: tuple[str, ...]
    warnings: tuple[str, ...]


CORE_REQUIRED = (
    "BOT_TOKEN",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "LIGA_CHANNEL_ID",
    "GIFTS_CHANNEL_ID",
    "LLM_API_KEY",
)

SHORTS_REQUIRED = (
    "SHORTS_WORKER_URL",
    "YANDEX_SPEECHKIT_API_KEY",
    "YANDEX_CLOUD_FOLDER_ID",
)


def evaluate_release(env: Mapping[str, str], require_shorts: bool = True) -> GateResult:
    """Fail closed before switching Content OS v2 into production.

    Values are never returned, logged or persisted: the gate only checks presence.
    """
    blocking = [f"missing:{key}" for key in CORE_REQUIRED if not str(env.get(key, "")).strip()]
    if require_shorts:
        blocking.extend(f"missing:{key}" for key in SHORTS_REQUIRED if not str(env.get(key, "")).strip())

    warnings: list[str] = []
    if str(env.get("CONTENT_OS_RUNTIME", "legacy")).lower() != "v2":
        warnings.append("runtime:not_v2")
    if str(env.get("SHORTS_ALLOW_EDGE_FALLBACK", "false")).lower() in {"1", "true", "yes"}:
        warnings.append("shorts:edge_fallback_enabled")
    if str(env.get("AUTO_PUBLISH", "false")).lower() in {"1", "true", "yes"}:
        warnings.append("publishing:auto_publish_enabled_during_rollout")

    return GateResult(not blocking, tuple(blocking), tuple(warnings))
