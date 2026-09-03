import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


def csv(name: str, default: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


@dataclass(frozen=True)
class Settings:
    bot_token: str
    shop_bot_token: str
    admins: frozenset[str]
    llm_key: str
    llm_url: str
    llm_model: str
    database_path: str
    supabase_url: str
    supabase_key: str
    timezone: ZoneInfo
    auto_publish: bool
    mpt_webhook_url: str
    mpt_base_url: str
    mpt_api_key: str
    mpt_voice_name: str
    mpt_timeout_minutes: int
    gift_asset_url: str
    gift_asset_key: str
    gift_asset_header: str
    gifts_supabase_url: str
    gifts_supabase_key: str
    gifts_signals_path: str
    telegram_api_id: int
    telegram_api_hash: str
    telegram_session: str
    publish_via_mtproto: bool
    course_channels: list[str]
    course_import_limit: int
    analytics_sync_minutes: int
    matchlens_base_url: str
    matchlens_api_key: str
    matchlens_timeout_minutes: int
    matchlens_upload_max_mb: int
    api_football_key: str
    api_football_url: str
    football_leagues: list[str]
    shop_cta_every: int
    channels: dict[str, str]
    schedules: dict[str, list[str]]


def load_settings() -> Settings:
    return Settings(
        bot_token=os.environ["BOT_TOKEN"],
        shop_bot_token=os.getenv("SHOP_BOT_TOKEN", "").strip(),
        admins=frozenset(x.lower().lstrip("@") for x in csv("ADMIN_USERNAMES", "skillell")),
        llm_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_url=os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/"),
        llm_model=os.getenv("LLM_MODEL", "gemini-2.5-flash-lite"),
        database_path=os.getenv("DATABASE_PATH", "/data/content_os.db"),
        supabase_url=os.getenv("SUPABASE_URL", "").rstrip("/"),
        supabase_key=os.getenv("SUPABASE_KEY", "").strip(),
        timezone=ZoneInfo(os.getenv("TIMEZONE", "Asia/Yekaterinburg")),
        auto_publish=os.getenv("AUTO_PUBLISH", "false").lower() in {"1", "true", "yes"},
        mpt_webhook_url=os.getenv("MPT_WEBHOOK_URL", "").strip(),
        mpt_base_url=os.getenv("MPT_BASE_URL", "").strip().rstrip("/"),
        mpt_api_key=os.getenv("MPT_API_KEY", "").strip(),
        mpt_voice_name=os.getenv("MPT_VOICE_NAME", "ru-RU-DmitryNeural").strip(),
        mpt_timeout_minutes=max(3,int(os.getenv("MPT_TIMEOUT_MINUTES", "20"))),
        gift_asset_url=os.getenv("GIFT_ASSET_BASE_URL", "https://giftasset.gifts").rstrip("/"),
        gift_asset_key=os.getenv("GIFT_ASSET_API_KEY", "").strip(),
        gift_asset_header=os.getenv("GIFT_ASSET_API_HEADER", "X-API-Key").strip(),
        gifts_supabase_url=os.getenv("GIFTS_SUPABASE_URL", "").rstrip("/"),
        gifts_supabase_key=os.getenv("GIFTS_SUPABASE_KEY", "").strip(),
        gifts_signals_path=os.getenv("GIFTS_SIGNALS_PATH", "").strip().lstrip("/"),
        telegram_api_id=int(os.getenv("TELEGRAM_API_ID", "0") or 0),
        telegram_api_hash=os.getenv("TELEGRAM_API_HASH", "").strip(),
        telegram_session=os.getenv("TELEGRAM_SESSION_STRING", "").strip(),
        publish_via_mtproto=os.getenv("PUBLISH_VIA_MTPROTO", "false").lower() in {"1","true","yes"},
        course_channels=csv("COURSE_CHANNELS", ""),
        course_import_limit=max(20,min(500,int(os.getenv("COURSE_IMPORT_LIMIT","150")))),
        analytics_sync_minutes=max(15,int(os.getenv("ANALYTICS_SYNC_MINUTES", "60"))),
        matchlens_base_url=os.getenv("MATCHLENS_BASE_URL", "").strip().rstrip("/"),
        matchlens_api_key=os.getenv("MATCHLENS_API_KEY", "").strip(),
        matchlens_timeout_minutes=max(10,int(os.getenv("MATCHLENS_TIMEOUT_MINUTES", "180"))),
        matchlens_upload_max_mb=max(5,int(os.getenv("MATCHLENS_UPLOAD_MAX_MB", "100"))),
        api_football_key=os.getenv("API_FOOTBALL_KEY", "").strip(),
        api_football_url=os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io").strip().rstrip("/"),
        football_leagues=csv("FOOTBALL_LEAGUES", "39,140,135,78,61,2,3"),
        shop_cta_every=max(0,int(os.getenv("SHOP_CTA_EVERY", "4"))),
        channels={"liga": os.getenv("LIGA_CHANNEL_ID", "@LigaProgress"),
                  "gifts": os.getenv("GIFTS_CHANNEL_ID", "@GiftsIntelligence")},
        schedules={"liga": csv("LIGA_DRAFT_TIMES", "09:00,15:00,20:00"),
                   "gifts": csv("GIFTS_DRAFT_TIMES", "11:00,17:00,21:30")},
    )
