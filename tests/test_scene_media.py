from pathlib import Path

from shorts_service.scene_media import SUPPORTED_ASSET_TYPES, compile_scene_specs, write_text_card_copy


def test_scene_specs_preserve_ratios_and_match_audio_duration():
    payload = {"scenes": [
        {"seconds": 2, "visual": "market", "asset_type": "stock_video"},
        {"seconds": 3, "screen_text": "НЕ СМОТРИ ТОЛЬКО НА FLOOR", "asset_type": "text_scene"},
    ]}
    specs = compile_scene_specs(payload, 10)
    assert len(specs) == 2
    assert round(sum(item.seconds for item in specs), 2) == 10
    assert round(specs[0].seconds / specs[1].seconds, 2) == round(2 / 3, 2)


def test_text_card_copy_uses_screen_text(tmp_path: Path):
    scene = compile_scene_specs({"scenes": [{"seconds": 2, "screen_text": "СМОТРИ MODEL, НЕ ТОЛЬКО FLOOR", "asset_type": "text_scene"}]}, 2)[0]
    path = tmp_path / "scene.txt"
    write_text_card_copy(path, scene)
    assert "СМОТРИ MODEL" in path.read_text("utf-8")


def test_worker_declares_only_assets_it_really_renders_natively():
    assert SUPPORTED_ASSET_TYPES == {"stock_video", "text_scene"}
