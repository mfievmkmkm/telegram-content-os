from types import SimpleNamespace

from content_os.shorts.models import ShortBrief, ShortScene
from content_os.shorts.orchestrator import ShortsStudio


class DummyDB:
    pass


class DummyEditor:
    pass


def test_worker_payload_preserves_stage_choices():
    settings = SimpleNamespace(mpt_base_url="", mpt_api_key="", mpt_timeout_minutes=10)
    studio = ShortsStudio(settings, DummyEditor(), DummyDB())
    brief = ShortBrief(
        title="Title",
        hook="Hook",
        voiceover=" ".join(["слово"] * 48),
        scenes=[
            ShortScene(4, "NFT marketplace smartphone", "СМОТРИ", "stock_video"),
            ShortScene(4, "market snapshot", "НЕ FLOOR", "market_chart"),
            ShortScene(4, "gift screenshot", "MODEL", "screenshot"),
            ShortScene(4, "reaction meme", "УЖЕ КУПИЛИ", "meme"),
            ShortScene(4, "dark interface", "ПРОВЕРЬ", "stock_video"),
            ShortScene(4, "final CTA", "ЗАЙДИ", "text_scene"),
        ],
        caption="caption",
        music_mood="dark tension",
        cta="Проверь модель",
        channel="gifts",
        voice_preset="ru_lera",
        subtitle_preset="clean",
        delivery_preset="punchy",
    )
    payload = studio.worker_payload(brief)
    assert payload["voice_provider"] == "speechkit"
    assert payload["voice_name"] == "lera"
    assert payload["subtitle_preset"] == "clean"
    assert payload["scenes"][1]["asset_type"] == "market_chart"
    assert payload["video_source"] == "scene_assets"
