from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class GateResult:
    ready: bool
    blocking: tuple[str, ...]
    warnings: tuple[str, ...]


EDITOR_REQUIRED = (
    "BOT_TOKEN",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "LIGA_CHANNEL_ID",
    "GIFTS_CHANNEL_ID",
    "LLM_API_KEY",
)

EDITOR_SHORTS_REQUIRED = (
    "MPT_BASE_URL",
    "MPT_API_KEY",
)

SHORTS_WORKER_REQUIRED = (
    "SHORTS_API_KEY",
    "PEXELS_API_KEY",
    "YANDEX_SPEECHKIT_API_KEY",
    "YANDEX_CLOUD_FOLDER_ID",
)


def _missing(env: Mapping[str, str], keys: tuple[str, ...]) -> list[str]:
    return [f"missing:{key}" for key in keys if not str(env.get(key, "")).strip()]


def evaluate_release(env: Mapping[str, str], require_shorts: bool = True) -> GateResult:
    """Check the Content OS editor service before enabling v2.

    Worker-only secrets are deliberately not required here because Railway services
    keep their environments isolated.
    """
    blocking = _missing(env, EDITOR_REQUIRED)
    if require_shorts:
        blocking.extend(_missing(env, EDITOR_SHORTS_REQUIRED))

    warnings: list[str] = []
    if str(env.get("CONTENT_OS_RUNTIME", "legacy")).lower() != "v2":
        warnings.append("runtime:not_v2")
    if str(env.get("AUTO_PUBLISH", "false")).lower() in {"1", "true", "yes"}:
        warnings.append("publishing:auto_publish_enabled_during_rollout")
    if not str(env.get("SHOP_BOT_TOKEN", "")).strip():
        warnings.append("sales:shop_bot_disabled")

    return GateResult(not blocking, tuple(blocking), tuple(warnings))


def evaluate_shorts_worker(env: Mapping[str, str]) -> GateResult:
    """Check the isolated Shorts Worker environment without exposing secret values."""
    blocking = _missing(env, SHORTS_WORKER_REQUIRED)
    warnings: list[str] = []
    if str(env.get("SHORTS_ALLOW_EDGE_FALLBACK", "false")).lower() in {"1", "true", "yes"}:
        warnings.append("shorts:edge_fallback_enabled")
    data_dir = str(env.get("SHORTS_DATA_DIR", "/data")).strip() or "/data"
    if data_dir != "/data":
        warnings.append("shorts:persistence_not_on_data_volume")
    return GateResult(not blocking, tuple(blocking), tuple(warnings))
