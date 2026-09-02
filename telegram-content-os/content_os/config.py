import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


def csv(name: str, default: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admins: frozenset[str]
    llm_key: str
    llm_url: str
    llm_model: str
    database_path: str
    timezone: ZoneInfo
    auto_publish: bool
    mpt_webhook_url: str
    gift_asset_url: str
    gift_asset_key: str
    gift_asset_header: str
    gifts_supabase_url: str
    gifts_supabase_key: str
    gifts_signals_path: str
    telegram_api_id: int
    telegram_api_hash: str
    telegram_session: str
    analytics_sync_minutes: int
    channels: dict[str, str]
    schedules: dict[str, list[str]]


def load_settings() -> Settings:
    return Settings(
        bot_token=os.environ["BOT_TOKEN"],
        admins=frozenset(x.lower().lstrip("@") for x in csv("ADMIN_USERNAMES", "skillell")),
        llm_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_url=os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/"),
        llm_model=os.getenv("LLM_MODEL", "gemini-2.5-flash-lite"),
        database_path=os.getenv("DATABASE_PATH", "/data/content_os.db"),
        timezone=ZoneInfo(os.getenv("TIMEZONE", "Asia/Yekaterinburg")),
        auto_publish=os.getenv("AUTO_PUBLISH", "false").lower() in {"1", "true", "yes"},
        mpt_webhook_url=os.getenv("MPT_WEBHOOK_URL", "").strip(),
        gift_asset_url=os.getenv("GIFT_ASSET_BASE_URL", "https://giftasset.gifts").rstrip("/"),
        gift_asset_key=os.getenv("GIFT_ASSET_API_KEY", "").strip(),
        gift_asset_header=os.getenv("GIFT_ASSET_API_HEADER", "X-API-Key").strip(),
        gifts_supabase_url=os.getenv("GIFTS_SUPABASE_URL", "").rstrip("/"),
        gifts_supabase_key=os.getenv("GIFTS_SUPABASE_KEY", "").strip(),
        gifts_signals_path=os.getenv("GIFTS_SIGNALS_PATH", "").strip().lstrip("/"),
        telegram_api_id=int(os.getenv("TELEGRAM_API_ID", "0") or 0),
        telegram_api_hash=os.getenv("TELEGRAM_API_HASH", "").strip(),
        telegram_session=os.getenv("TELEGRAM_SESSION_STRING", "").strip(),
        analytics_sync_minutes=max(15,int(os.getenv("ANALYTICS_SYNC_MINUTES", "60"))),
        channels={"liga": os.getenv("LIGA_CHANNEL_ID", "@LigaProgress"),
                  "gifts": os.getenv("GIFTS_CHANNEL_ID", "@GiftsIntelligence")},
        schedules={"liga": csv("LIGA_DRAFT_TIMES", "09:00,15:00,20:00"),
                   "gifts": csv("GIFTS_DRAFT_TIMES", "11:00,17:00,21:30")},
    )
