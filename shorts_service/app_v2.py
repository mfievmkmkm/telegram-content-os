from __future__ import annotations

import json
import math
import os
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
    from .subtitles import ass_subtitles_v2
    from .tts import TTSRouter
except ImportError:
    import app as legacy
    from core import clean_script, unique_terms
    from subtitles import ass_subtitles_v2
    from tts import TTSRouter


DATA = legacy.DATA
JOBS = legacy.JOBS
TASKS = legacy.TASKS
API_KEY = legacy.API_KEY
PEXELS_KEY = legacy.PEXELS_KEY
TTS = TTSRouter()
app = FastAPI(title="Content OS Shorts Worker", version="2.0")


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
        "version": "2.0",
        "pexels": bool(PEXELS_KEY),
        "persistent": str(DATA) == "/data",
        "tts": providers,
        "voice": "speechkit" if providers.get("speechkit") else "elevenlabs" if providers.get("elevenlabs") else "edge-fallback" if TTS.allow_edge_fallback else "not-configured",
        "staged": True,
        "subtitle_presets": ["punch", "clean", "sport", "meme"],
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
        job.update(progress=20, stage="scenes")
        write_job(job)

        clips = await legacy.pexels_clips(scene_terms(payload), folder)
        if len(clips) < 3:
            raise RuntimeError("Pexels вернул меньше трёх пригодных видеоклипов")

        job.update(progress=42, stage="render")
        write_job(job)
        cut = 1.7
        count = math.ceil(duration / cut)
        normalized = []
        for index in range(count):
            source = clips[index % len(clips)]
            output = folder / f"part-{index}.mp4"
            offset = (index // len(clips)) * 1.7
            x = (-18, 0, 18)[index % 3]
            y = (-30, 0, 30)[index % 3]
            legacy.run([
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(source), "-ss", f"{offset:.1f}", "-t", str(cut),
                "-vf", f"scale=760:1352:force_original_aspect_ratio=increase,crop=720:1280:(iw-ow)/2+{x}:(ih-oh)/2+{y},eq=contrast=1.04:saturation=1.08,fps=25",
                "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-threads", "1",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
            ])
            normalized.append(output)
            job["progress"] = 42 + int((index + 1) / count * 32)
            write_job(job)

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
        # Keep status JSON, aggressively remove disposable media to avoid Railway disk exhaustion.
        for item in folder.glob("*"):
            try:
                if item.is_file() and item.name != "payload.json":
                    item.unlink(missing_ok=True)
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
            except OSError:
                pass
