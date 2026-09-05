from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import textwrap


@dataclass(frozen=True)
class SceneSpec:
    seconds: float
    visual: str
    screen_text: str
    asset_type: str
    asset_ref: str = ""


def compile_scene_specs(payload: dict, audio_duration: float) -> list[SceneSpec]:
    raw = payload.get("scenes") or []
    specs: list[SceneSpec] = []
    for item in raw:
        try:
            seconds = float(item.get("seconds") or 0)
        except (TypeError, ValueError):
            seconds = 0
        if seconds <= 0:
            continue
        specs.append(SceneSpec(
            seconds=seconds,
            visual=str(item.get("visual") or "").strip(),
            screen_text=str(item.get("screen_text") or "").strip(),
            asset_type=str(item.get("asset_type") or "stock_video").strip().lower(),
            asset_ref=str(item.get("asset_ref") or "").strip(),
        ))
    if not specs:
        return [SceneSpec(max(1.0, audio_duration), str(payload.get("video_subject") or ""), "", "stock_video")]

    total = sum(item.seconds for item in specs)
    scale = audio_duration / total if total > 0 else 1.0
    # Preserve editorial timing proportions while matching the actual synthesized voice.
    return [SceneSpec(max(.75, item.seconds * scale), item.visual, item.screen_text, item.asset_type, item.asset_ref) for item in specs]


def write_text_card_copy(path: Path, scene: SceneSpec) -> None:
    text = scene.screen_text or scene.visual or "Content OS"
    wrapped = "\n".join(textwrap.wrap(" ".join(text.split()), width=24)[:6])
    path.write_text(wrapped, "utf-8")


def text_card_filter(textfile: Path, channel: str) -> str:
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    label = "GIFTS INTELLIGENCE" if channel == "gifts" else "LIGA PROGRESS"
    # textfile avoids escaping Russian copy inside the ffmpeg filter string.
    return (
        "scale=720:1280,"
        "drawbox=x=40:y=360:w=640:h=560:color=black@0.38:t=fill,"
        f"drawtext=fontfile={font}:text='{label}':fontsize=27:fontcolor=white@0.72:x=(w-text_w)/2:y=405,"
        f"drawtext=fontfile={font}:textfile='{textfile}':fontsize=52:fontcolor=white:"
        "x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=16:fix_bounds=true,"
        "fps=25"
    )


SUPPORTED_ASSET_TYPES = {"stock_video", "text_scene"}
