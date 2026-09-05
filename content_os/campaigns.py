from __future__ import annotations

from dataclasses import dataclass


PROJECT_CODES = {"gifts": "g", "liga": "l", "services": "a"}
FORMAT_CODES = {"post": "p", "shorts": "s", "meme": "m", "card": "c", "unknown": "u"}
REVERSE_PROJECT = {value: key for key, value in PROJECT_CODES.items()}
REVERSE_FORMAT = {value: key for key, value in FORMAT_CODES.items()}


def _slug(value: str, limit: int) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum() or ch in "-")[:limit]


@dataclass(frozen=True, slots=True)
class CampaignRef:
    project: str
    content_id: int
    format_key: str = "unknown"
    offer: str = ""
    campaign: str = ""

    def token(self) -> str:
        project = PROJECT_CODES.get(self.project, "x")
        format_code = FORMAT_CODES.get(self.format_key, "u")
        offer = _slug(self.offer, 18)
        campaign = _slug(self.campaign, 12)
        parts = ["c", project, str(int(self.content_id)), format_code]
        if offer or campaign:
            parts.append(offer or "-")
        if campaign:
            parts.append(campaign)
        return "_".join(parts)[:64]


def parse_campaign(token: str) -> CampaignRef | None:
    parts = (token or "").strip().split("_")
    if len(parts) < 4 or parts[0] != "c" or not parts[2].isdigit():
        return None
    project = REVERSE_PROJECT.get(parts[1])
    if not project:
        return None
    offer = parts[4] if len(parts) > 4 and parts[4] != "-" else ""
    campaign = parts[5] if len(parts) > 5 else ""
    return CampaignRef(
        project=project,
        content_id=int(parts[2]),
        format_key=REVERSE_FORMAT.get(parts[3], "unknown"),
        offer=offer[:18],
        campaign=campaign[:12],
    )


def campaign_source(ref: CampaignRef) -> str:
    parts = [ref.project, ref.format_key, str(ref.content_id)]
    if ref.offer:
        parts.append(ref.offer)
    if ref.campaign:
        parts.append(ref.campaign)
    return ":".join(parts)
