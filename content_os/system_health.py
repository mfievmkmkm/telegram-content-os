from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class SubsystemStatus:
    key: str
    title: str
    ready: bool
    missing: tuple[str, ...] = ()
    warning: str = ""


def _status(key: str, title: str, env: Mapping[str, str], required: tuple[str, ...], warning: str = "") -> SubsystemStatus:
    missing = tuple(name for name in required if not str(env.get(name, "")).strip())
    return SubsystemStatus(key, title, not missing, missing, warning if not missing else "")


def subsystem_statuses(env: Mapping[str, str]) -> tuple[SubsystemStatus, ...]:
    """Static preflight by subsystem; never exposes secret values."""
    statuses = [
        _status("editor", "Editor", env, ("BOT_TOKEN", "LLM_API_KEY", "LIGA_CHANNEL_ID", "GIFTS_CHANNEL_ID")),
        _status("database", "Supabase", env, ("SUPABASE_URL", "SUPABASE_KEY")),
        _status("shorts_editor", "Shorts client", env, ("MPT_BASE_URL", "MPT_API_KEY")),
        _status("shorts_worker", "Shorts worker", env, ("SHORTS_API_KEY", "PEXELS_API_KEY", "YANDEX_SPEECHKIT_API_KEY", "YANDEX_CLOUD_FOLDER_ID")),
    ]

    if str(env.get("SHOP_BOT_TOKEN", "")).strip():
        statuses.append(_status("shop", "Shop bot", env, ("SHOP_BOT_TOKEN",)))
    else:
        statuses.append(SubsystemStatus("shop", "Shop", True, (), "встроен в editor runtime"))

    mtproto_enabled = str(env.get("PUBLISH_VIA_MTPROTO", "false")).lower() in {"1", "true", "yes"}
    if mtproto_enabled:
        statuses.append(_status("premium_publish", "Premium publish", env, ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION_STRING")))
    else:
        statuses.append(SubsystemStatus("premium_publish", "Premium publish", True, (), "выключен; Bot API остаётся fallback"))

    if str(env.get("MATCHLENS_BASE_URL", "")).strip():
        statuses.append(_status("matchlens", "MatchLens", env, ("MATCHLENS_BASE_URL", "MATCHLENS_API_KEY"), "experimental"))
    else:
        statuses.append(SubsystemStatus("matchlens", "MatchLens", True, (), "experimental/off"))
    if str(env.get("MINIAPP_PORT", "0")).strip() not in {"", "0"}:
        statuses.append(_status("miniapp", "Telegram Mini App", env, ("MINIAPP_PUBLIC_URL",)))
    else:
        statuses.append(SubsystemStatus("miniapp", "Telegram Mini App", True, (), "off"))
    return tuple(statuses)


def blocking_subsystems(env: Mapping[str, str]) -> tuple[SubsystemStatus, ...]:
    return tuple(item for item in subsystem_statuses(env) if not item.ready and item.key in {"editor", "database", "shorts_editor", "shorts_worker"})
