from __future__ import annotations

from dataclasses import dataclass

from ..campaigns import CampaignRef, campaign_source


@dataclass(frozen=True)
class TrackedCTA:
    label: str
    url: str
    token: str
    source: str


def telegram_deep_link(bot_username: str, ref: CampaignRef, label: str = "Открыть →") -> TrackedCTA:
    username = (bot_username or "").strip().lstrip("@").strip()
    if not username:
        raise ValueError("bot username is required")
    token = ref.token()
    if len(token) > 64:
        raise ValueError("Telegram start payload exceeds 64 characters")
    return TrackedCTA(
        label=label.strip() or "Открыть →",
        url=f"https://t.me/{username}?start={token}",
        token=token,
        source=campaign_source(ref),
    )
