from types import SimpleNamespace

import content_os.shorts.orchestrator as orchestrator
from content_os.shorts.models import ShortBrief, ShortScene
from content_os.shorts.orchestrator import ShortsStudio


class DB:
    def draft(self, draft_id):
        return {"id": draft_id, "text": "Смотри MODEL, а не только FLOOR", "format_key": "разбор_ошибки"}


class Editor:
    pass


def test_brand_card_scene_gets_inline_png_asset(monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 20
    monkeypatch.setattr(orchestrator, "render_card", lambda *args, **kwargs: png)
    settings = SimpleNamespace(mpt_base_url="", mpt_api_key="")
    studio = ShortsStudio(settings, Editor(), DB())
    brief = ShortBrief(
        title="test", hook="hook", voiceover="слово " * 25,
        scenes=[ShortScene(2.0, "card", asset_type="brand_card")],
        caption="", music_mood="", cta="", channel="gifts", draft_id=8,
    )
    scene = studio._scene_payloads(brief)[0]
    assert scene["asset_ref"].startswith("data:image/png;base64,")
