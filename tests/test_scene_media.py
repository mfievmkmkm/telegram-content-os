import asyncio
import base64
from pathlib import Path

import pytest

from shorts_service.scene_media import IMAGE_ASSET_TYPES, SUPPORTED_ASSET_TYPES, _public_https_url, compile_scene_specs, download_image_asset, write_text_card_copy


PNG_1X1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


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


def test_worker_declares_image_assets_as_native_when_asset_ref_is_available():
    assert {"brand_card", "screenshot", "meme", "market_chart", "generated_image", "user_asset"} == IMAGE_ASSET_TYPES
    assert {"stock_video", "text_scene"}.issubset(SUPPORTED_ASSET_TYPES)
    assert IMAGE_ASSET_TYPES.issubset(SUPPORTED_ASSET_TYPES)


def test_remote_asset_guard_rejects_non_https_and_private_hosts():
    assert not _public_https_url("http://example.com/a.png")
    assert not _public_https_url("https://localhost/a.png")
    assert not _public_https_url("https://127.0.0.1/a.png")
    assert not _public_https_url("file:///etc/passwd")


def test_inline_png_asset_is_written_without_network(tmp_path: Path):
    ref = "data:image/png;base64," + base64.b64encode(PNG_1X1).decode("ascii")
    path = asyncio.run(download_image_asset(ref, tmp_path / "card.img"))
    assert path.read_bytes() == PNG_1X1


def test_inline_asset_rejects_non_png_payload(tmp_path: Path):
    ref = "data:image/png;base64," + base64.b64encode(b"not-a-png").decode("ascii")
    with pytest.raises(ValueError, match="must be PNG"):
        asyncio.run(download_image_asset(ref, tmp_path / "bad.img"))
