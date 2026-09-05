from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ProjectKind(str, Enum):
    GIFTS = "gifts"
    LIGA = "liga"
    SERVICES = "services"


class AssetKind(str, Enum):
    POST = "post"
    CARD = "card"
    SHORT = "short"
    MEME = "meme"
    CHALLENGE = "challenge"
    AUDIO = "audio"


@dataclass(frozen=True)
class Project:
    key: str
    title: str
    kind: ProjectKind


@dataclass(frozen=True)
class ContentItem:
    id: str
    project_key: str
    topic: str
    format: str
    status: str = "draft"
    campaign_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Asset:
    id: str
    content_id: str
    kind: AssetKind
    uri: str
    version: int = 1


@dataclass(frozen=True)
class Campaign:
    id: str
    project_key: str
    offer_key: str = ""
    source: str = "telegram"


@dataclass(frozen=True)
class Experiment:
    id: str
    content_id: str
    variable: str
    control: str
    variant: str


@dataclass(frozen=True)
class Product:
    key: str
    title: str
    outcome: str
    active: bool = True


@dataclass(frozen=True)
class Order:
    id: str
    product_key: str
    campaign_id: str = ""
    status: str = "new"


@dataclass(frozen=True)
class KnowledgeItem:
    id: str
    domain: str
    kind: str
    text: str
    source: str = ""


@dataclass(frozen=True)
class ShortJob:
    id: str
    content_id: str
    stage: str = "script"
    status: str = "draft"


@dataclass(frozen=True)
class Player:
    id: str
    display_name: str
    position: str = "all"
