from __future__ import annotations

from dataclasses import dataclass


PROJECT_CODES = {"gifts": "g", "liga": "l", "services": "a"}
FORMAT_CODES = {"post": "p", "shorts": "s", "meme": "m", "card": "c", "unknown": "u"}
REVERSE_PROJECT = {value: key for key, value in PROJECT_CODES.items()}
REVERSE_FORMAT = {value: key for key, value in FORMAT_CODES.items()}


@dataclass(frozen=True, slots=True)
class CampaignRef:
    project: str
    content_id: int
    format_key: str = "unknown"
    offer: str = ""

    def token(self) -> str:
        project = PROJECT_CODES.get(self.project, "x")
        format_code = FORMAT_CODES.get(self.format_key, "u")
        offer = "".join(ch for ch in self.offer.lower() if ch.isalnum() or ch in "_-")[:18]
        token = f"c_{project}_{int(self.content_id)}_{format_code}"
        if offer:
            token += f"_{offer}"
        return token[:64]


def parse_campaign(token: str) -> CampaignRef | None:
    parts = (token or "").strip().split("_")
    if len(parts) < 4 or parts[0] != "c" or not parts[2].isdigit():
        return None
    project = REVERSE_PROJECT.get(parts[1])
    if not project:
        return None
    return CampaignRef(
        project=project,
        content_id=int(parts[2]),
        format_key=REVERSE_FORMAT.get(parts[3], "unknown"),
        offer="_".join(parts[4:])[:18] if len(parts) > 4 else "",
    )


def campaign_source(ref: CampaignRef) -> str:
    return f"{ref.project}:{ref.format_key}:{ref.content_id}"
