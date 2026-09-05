from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

try:
    from . import app as legacy
    from .core import clean_script, unique_terms
    from .scene_media import (
        IMAGE_ASSET_TYPES,
        SUPPORTED_ASSET_TYPES,
        compile_scene_specs,
        download_image_asset,
        image_filter,
        text_card_filter,
        write_text_card_copy,
    )
    from .subtitles import ass_subtitles_v2
    from .tts import TTSRouter
except ImportError:
    import app as legacy
    from core import clean_script, unique_terms
    from scene_media import (
        IMAGE_ASSET_TYPES,
        SUPPORTED_ASSET_TYPES,
        compile_scene_specs,
        download_image_asset,
        image_filter,
        text_card_filter,
        write_text_card_copy,
    )
    from subtitles import ass_subtitles_v2
    from tts import TTSRouter


DATA = legacy.DATA
JOBS = legacy.JOBS
TASKS = legacy.TASKS
API_KEY = legacy.API_KEY
PEXELS_KEY = legacy.PEXELS_KEY
TTS = TTSRouter()
app = FastAPI(title="Content OS Shorts Worker", version="2.2")


@app.on_event("startup")
def startup_cleanup():
    legacy.startup_cleanup()


def authorize(value):
    legacy.authorize(value)


def read_job(task_id):
    return legacy.read_job(task_id)


def write_job(job):
    legacy.write_job(job)


@app.get("/health")
def health():
    providers = TTS.health()
    return {
        "ok": True,
        "service": "content-os-shorts",
        "version": "2.2",
        "pexels": bool(PEXELS_KEY),
        "persistent": str(DATA) == "/data",
        "tts": providers,
        "voice": "speechkit" if providers.get("speechkit") else "elevenlabs" if providers.get("elevenlabs") else "edge-fallback" if TTS.allow_edge_fallback else "not-configured",
        "staged": True,
        "subtitle_presets": ["punch", "clean", "sport", "meme"],
        "asset_types": sorted(SUPPORTED_ASSET_TYPES),
        "remote_image_assets": sorted(IMAGE_ASSET_TYPES),
        "unsupported_asset_policy": "text_scene_fallback",
    }


@app.post("/api/v1/videos")
def create(payload: dict, background: BackgroundTasks, x_api_key: str | None = Header(None)):
    authorize(x_api_key)
    legacy.cleanup_stale()
    task_id = str(uuid.uuid4())
    folder = TASKS / task_id
    folder.mkdir(parents=True, exist_ok=True)
    job = {"task_id": task_id, "state": 0, "progress": 0, "videos": [], "error": "", "stage": "queued"}
    write_job(job)
    (folder / "payload.json").write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
    background.add_task(render, task_id, payload)
    return {"status": 200, "data": {"task_id": task_id}}


@app.get("/api/v1/tasks/{task_id}")
def status(task_id: str, x_api_key: str | None = Header(None)):
    authorize(x_api_key)
    return {"status": 200, "data": read_job(task_id)}


@app.get("/files/{task_id}.mp4")
def video(task_id: str):
    path = TASKS / task_id / "shorts.mp4"
    if not path.exists():
        raise HTTPException(404, "video not ready")
    return FileResponse(path, media_type="video/mp4", filename=f"shorts-{task_id}.mp4", background=BackgroundTask(legacy.remove_task, task_id))


def scene_terms(payload: dict) -> list[str]:
    result = []
    for scene in payload.get("scenes") or []:
        if str(scene.get("asset_type") or "stock_video") != "stock_video":
            continue
        term = str(scene.get("visual") or "").strip()
        if term and term.lower() not in {item.lower() for item in result}:
            result.append(term)
    for term in unique_terms(payload):
        if term.lower() not in {item.lower() for item in result}:
            result.append(term)
    channel = str(payload.get("brand_channel") or payload.get("channel") or "liga")
    fallback = (
        ["NFT marketplace smartphone", "digital collectible dark interface", "crypto chart mobile"]
        if channel == "gifts"
        else ["football training", "soccer tactical board", "athlete sprint field"]
    )
    for term in fallback:
        if term.lower() not in {item.lower() for item in result}:
            result.append(term)
    return result[:10]


def _render_text_scene(folder: Path, index: int, seconds: float, scene, channel: str) -> Path:
    copy_path = folder / f"scene-{index}.txt"
    write_text_card_copy(copy_path, scene)
    output = folder / f"part-{index}.mp4"
    legacy.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x111111:s=720x1280:r=25",
        "-t", f"{seconds:.3f}", "-vf", text_card_filter(copy_path, channel),
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-threads", "1",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ])
    return output


def _render_image_scene(folder: Path, index: int, seconds: float, image: Path) -> Path:
    output = folder / f"part-{index}.mp4"
    legacy.run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(image), "-t", f"{seconds:.3f}",
        "-vf", image_filter(), "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-threads", "1",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ])
    return output


async def render(task_id: str, payload: dict):
    job = read_job(task_id)
    folder = TASKS / task_id
    try:
        script = clean_script(payload.get("video_script") or payload.get("voiceover") or payload.get("video_subject") or "")
        words = script.split()
        if not 20 <= len(words) <= 70:
            raise RuntimeError(f"Сценарий должен содержать 20–70 слов, сейчас {len(words)}")
        tail = words[-1].strip(".,!?—–:;") if words else ""
        if len(tail) == 1 and tail.isalpha():
            raise RuntimeError("Сценарий оборван на последнем слове")
        script = re.sub(r"\s+([,.!?])", r"\1", script)
        script = re.sub(r"([!?]){2,}", r"\1", script)
        script = " ".join(script.strip().split())

        job.update(progress=5, stage="voice")
        write_job(job)
        provider = str(payload.get("voice_provider") or "speechkit")
        voice = str(payload.get("voice_name") or "lera")
        speed = float(payload.get("voice_rate") or 1.04)
        tts = await TTS.synthesize(provider, script, folder / "voice.mp3", voice, speed)
        job.update(voice_provider=tts.provider, voice_error=tts.warning)
        write_job(job)

        probe = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(folder / "voice.mp3")
        ], text=True)
        duration = max(8.0, float(probe.strip()))
        specs = compile_scene_specs(payload, duration)
        channel = str(payload.get("brand_channel") or payload.get("channel") or "liga")
        job.update(progress=20, stage="scenes", scene_count=len(specs))
        write_job(job)

        stock_needed = any(scene.asset_type == "stock_video" for scene in specs)
        clips = await legacy.pexels_clips(scene_terms(payload), folder) if stock_needed else []
        fallbacks: list[str] = []
        normalized: list[Path] = []
        stock_cursor = 0
        part_index = 0

        for scene_index, scene in enumerate(specs):
            if scene.asset_type == "stock_video" and clips:
                pieces = max(1, math.ceil(scene.seconds / 2.2))
                piece_duration = scene.seconds / pieces
                for _ in range(pieces):
                    source = clips[stock_cursor % len(clips)]
                    stock_cursor += 1
                    output = folder / f"part-{part_index}.mp4"
                    offset = (stock_cursor // max(1, len(clips))) * 1.3
                    x = (-18, 0, 18)[part_index % 3]
                    y = (-30, 0, 30)[part_index % 3]
                    legacy.run([
                        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(source), "-ss", f"{offset:.1f}", "-t", f"{piece_duration:.3f}",
                        "-vf", f"scale=760:1352:force_original_aspect_ratio=increase,crop=720:1280:(iw-ow)/2+{x}:(ih-oh)/2+{y},eq=contrast=1.04:saturation=1.08,fps=25",
                        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-threads", "1",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
                    ])
                    normalized.append(output)
                    part_index += 1
            elif scene.asset_type in IMAGE_ASSET_TYPES and scene.asset_ref:
                try:
                    image_path = await download_image_asset(scene.asset_ref, folder / f"asset-{scene_index}.img")
                    normalized.append(_render_image_scene(folder, part_index, scene.seconds, image_path))
                    part_index += 1
                except Exception as exc:
                    fallbacks.append(f"{scene_index + 1}:{scene.asset_type}({type(exc).__name__})")
                    normalized.append(_render_text_scene(folder, part_index, scene.seconds, scene, channel))
                    part_index += 1
            else:
                if scene.asset_type != "text_scene":
                    reason = "stock_video_no_asset" if scene.asset_type == "stock_video" else f"{scene.asset_type}_no_ref"
                    fallbacks.append(f"{scene_index + 1}:{reason}")
                normalized.append(_render_text_scene(folder, part_index, scene.seconds, scene, channel))
                part_index += 1

            job["progress"] = 24 + int((scene_index + 1) / max(1, len(specs)) * 50)
            write_job(job)

        if not normalized:
            raise RuntimeError("Не удалось собрать ни одной сцены")

        render_warning = ""
        if fallbacks:
            render_warning = "Часть mixed-media сцен заменена на text scene: " + ", ".join(fallbacks[:8])
        job.update(render_warning=render_warning)
        (folder / "concat.txt").write_text("".join(f"file '{path.name}'\n" for path in normalized), "utf-8")
        preset = str(payload.get("subtitle_preset") or "punch")
        (folder / "subs.ass").write_text(ass_subtitles_v2(script, duration, preset, tts.alignment), "utf-8")
        job.update(progress=78, stage="captions")
        write_job(job)

        legacy.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(folder / "concat.txt"), "-i", str(folder / "voice.mp3"),
            "-vf", f"ass={folder / 'subs.ass'}", "-af", "apad=pad_dur=0.45", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-threads", "1", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-maxrate", "2800k", "-bufsize", "5600k", "-movflags", "+faststart", "-shortest", str(folder / "shorts.mp4"),
        ])
        job.update(state=1, progress=100, stage="ready", videos=[f"/files/{task_id}.mp4"], error="")
        write_job(job)
    except Exception as exc:
        job.update(state=-1, stage="failed", error=f"{type(exc).__name__}: {str(exc)[:700]}")
        write_job(job)
        for item in folder.glob("*"):
            try:
                if item.is_file() and item.name != "payload.json":
                    item.unlink(missing_ok=True)
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
            except OSError:
                pass
