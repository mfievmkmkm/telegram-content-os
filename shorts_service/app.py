from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import aiohttp
import edge_tts
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

try:
    from .core import ass_subtitles, clean_script, unique_terms
except ImportError:
    from core import ass_subtitles, clean_script, unique_terms

DATA=Path(os.getenv("SHORTS_DATA_DIR","/data")); JOBS=DATA/"jobs"; TASKS=DATA/"tasks"
for folder in (JOBS,TASKS): folder.mkdir(parents=True,exist_ok=True)
API_KEY=os.getenv("SHORTS_API_KEY","").strip(); PEXELS_KEY=os.getenv("PEXELS_API_KEY","").strip()
ELEVEN_KEY=os.getenv("ELEVENLABS_API_KEY","").strip(); ELEVEN_VOICE=os.getenv("ELEVENLABS_VOICE_ID","").strip()
ELEVEN_MODEL=os.getenv("ELEVENLABS_MODEL_ID","eleven_multilingual_v2").strip()
REQUIRE_ELEVEN=os.getenv("SHORTS_REQUIRE_ELEVENLABS","true").lower() in {"1","true","yes","on"}
app=FastAPI(title="Content OS Shorts Worker",version="1.0")


def remove_task(task_id:str,remove_job=True):
    shutil.rmtree(TASKS/task_id,ignore_errors=True)
    if remove_job:
        try: job_path(task_id).unlink(missing_ok=True)
        except OSError: pass


def cleanup_stale(max_age_seconds=1800):
    """Generated media is disposable; never let it fill the Railway volume."""
    now=time.time()
    for folder in TASKS.iterdir():
        try:
            if folder.is_dir() and now-folder.stat().st_mtime>max_age_seconds:
                remove_task(folder.name)
        except OSError: continue


@app.on_event("startup")
def startup_cleanup():
    # A deploy kills in-process renders, so every leftover task is stale.
    for folder in list(TASKS.iterdir()):
        if folder.is_dir(): remove_task(folder.name)


def authorize(value):
    if API_KEY and value!=API_KEY: raise HTTPException(401,"invalid api key")


def job_path(task_id): return JOBS/f"{task_id}.json"
def read_job(task_id):
    path=job_path(task_id)
    if not path.exists(): raise HTTPException(404,f"{task_id}: task not found")
    return json.loads(path.read_text("utf-8"))
def write_job(job):
    temp=job_path(job["task_id"]).with_suffix(".tmp"); temp.write_text(json.dumps(job,ensure_ascii=False),"utf-8"); temp.replace(job_path(job["task_id"]))


@app.get("/health")
def health(): return {"ok":True,"service":"content-os-shorts","pexels":bool(PEXELS_KEY),"persistent":str(DATA)=="/data",
                     "voice":"elevenlabs" if ELEVEN_KEY and ELEVEN_VOICE else "blocked" if REQUIRE_ELEVEN else "edge"}


@app.post("/api/v1/videos")
def create(payload:dict,background:BackgroundTasks,x_api_key:str|None=Header(None)):
    authorize(x_api_key); cleanup_stale(); task_id=str(uuid.uuid4()); folder=TASKS/task_id; folder.mkdir(parents=True,exist_ok=True)
    job={"task_id":task_id,"state":0,"progress":0,"videos":[],"error":""}; write_job(job)
    (folder/"payload.json").write_text(json.dumps(payload,ensure_ascii=False),"utf-8"); background.add_task(render,task_id,payload)
    return {"status":200,"data":{"task_id":task_id}}


@app.get("/api/v1/tasks/{task_id}")
def status(task_id:str,x_api_key:str|None=Header(None)):
    authorize(x_api_key); return {"status":200,"data":read_job(task_id)}


@app.get("/files/{task_id}.mp4")
def video(task_id:str):
    path=TASKS/task_id/"shorts.mp4"
    if not path.exists(): raise HTTPException(404,"video not ready")
    return FileResponse(path,media_type="video/mp4",filename=f"shorts-{task_id}.mp4",
                        background=BackgroundTask(remove_task,task_id))


async def pexels_clips(terms:list[str],folder:Path,limit=10)->list[Path]:
    if not PEXELS_KEY: raise RuntimeError("PEXELS_API_KEY не задан в Shorts Worker")
    urls=[]; headers={"Authorization":PEXELS_KEY}
    async with aiohttp.ClientSession(headers=headers,timeout=aiohttp.ClientTimeout(total=90)) as session:
        for term in terms:
            async with session.get("https://api.pexels.com/videos/search",params={"query":term,"per_page":8,"orientation":"portrait"}) as response:
                if response.status>=400: continue
                added=0
                for video in (await response.json()).get("videos",[]):
                    files=video.get("video_files") or []
                    vertical=[x for x in files if int(x.get("height") or 0)>int(x.get("width") or 0) and int(x.get("width") or 0)>=540]
                    candidates=vertical or files
                    if candidates:
                        choice=min(candidates,key=lambda x:abs(int(x.get("width") or 720)-720)); url=choice.get("link")
                        if url and url not in urls: urls.append(url); added+=1
                    if len(urls)>=limit or added>=2: break
            if len(urls)>=limit: break
        paths=[]
        for index,url in enumerate(urls):
            path=folder/f"source-{index}.mp4"
            async with session.get(url) as response:
                if response.status<400:
                    with path.open("wb") as target:
                        async for chunk in response.content.iter_chunked(1024*256): target.write(chunk)
                    paths.append(path)
        return paths


def run(command,timeout=900):
    result=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        log=(result.stderr or result.stdout or "").strip()
        if result.returncode in (-9,137):
            raise RuntimeError("FFmpeg остановлен из-за нехватки памяти. Worker должен работать в low-memory режиме")
        # The useful ffmpeg error is usually above the final output summary.
        lines=[line for line in log.splitlines() if line.strip()]
        important=[line for line in lines if any(marker in line.lower() for marker in (
            "error", "failed", "invalid", "unable", "cannot", "no such", "conversion failed"
        ))]
        detail="\n".join((important[-6:] or lines[-12:]))[-1200:]
        raise RuntimeError(f"FFmpeg exit {result.returncode}: {detail}")


async def synthesize(script:str,path:Path,voice:str,rate:str)->tuple[str,dict|None,str]:
    """Premium TTS when configured, free Edge voice as a resilient fallback."""
    if ELEVEN_KEY and ELEVEN_VOICE:
        url=f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}/with-timestamps"
        headers={"xi-api-key":ELEVEN_KEY,"Content-Type":"application/json","Accept":"audio/mpeg"}
        body={"text":script,"model_id":ELEVEN_MODEL,"voice_settings":{
            "stability":0.28,"similarity_boost":0.76,"style":0.62,"use_speaker_boost":True,"speed":1.12}}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                async with session.post(url,params={"output_format":"mp3_44100_128"},json=body,headers=headers) as response:
                    if response.status<400:
                        result=await response.json(); path.write_bytes(base64.b64decode(result["audio_base64"]))
                        return "elevenlabs",result.get("normalized_alignment") or result.get("alignment"),""
                    eleven_error=f"ElevenLabs HTTP {response.status}: {(await response.text())[:160]}"
        except Exception as exc: eleven_error=f"ElevenLabs {type(exc).__name__}: {str(exc)[:140]}"
    else: eleven_error="ELEVENLABS_API_KEY или ELEVENLABS_VOICE_ID не заполнены"
    if REQUIRE_ELEVEN:
        raise RuntimeError(f"ElevenLabs обязателен: {eleven_error}")
    await edge_tts.Communicate(script,voice=voice,rate=rate,pitch="+2Hz").save(str(path)); return "edge",None,eleven_error


async def render(task_id:str,payload:dict):
    job=read_job(task_id); folder=TASKS/task_id
    try:
        script=clean_script(payload.get("video_script") or payload.get("video_subject") or "")
        words=script.split()
        # Never cut a voiceover in the middle of a sentence. The editor must send a
        # complete short script; otherwise reject it before wasting stock footage.
        if len(words)>70: raise RuntimeError("Сценарий длиннее 70 слов — сократи его целиком, без обрыва финала")
        tail=words[-1].strip(".,!?—–:;") if words else ""
        if len(tail)==1 and tail.isalpha(): raise RuntimeError("Сценарий оборван на последнем слове")
        script=re.sub(r"\s+([,.!?])",r"\1",script)
        script=re.sub(r"([!?]){2,}",r"\1",script)
        script=" ".join(script.strip().split())
        if len(script)<30: raise RuntimeError("Сценарий озвучки слишком короткий")
        job["progress"]=5; write_job(job)
        voice=str(payload.get("voice_name") or "ru-RU-DmitryNeural")
        rate_value=float(payload.get("voice_rate") or 1.18); rate=f"{round((rate_value-1)*100):+d}%"
        job["voice_provider"],alignment,job["voice_error"]=await synthesize(script,folder/"voice.mp3",voice,rate); write_job(job)
        probe=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(folder/"voice.mp3")],text=True)
        duration=max(8.0,float(probe.strip())); job["progress"]=20; write_job(job)
        clips=await pexels_clips(unique_terms(payload),folder)
        if len(clips)<3: raise RuntimeError("Pexels вернул меньше трёх пригодных видеоклипов")
        job["progress"]=45; write_job(job); cut=1.7; count=math.ceil(duration/cut); normalized=[]
        for index in range(count):
            source=clips[index%len(clips)]
            output=folder/f"part-{index}.mp4"
            offset=(index//len(clips))*1.7
            x=(-20,0,20)[index%3]; y=(-36,0,36)[index%3]
            # 720p is Telegram-native enough and stays inside small Railway RAM limits.
            run(["ffmpeg","-y","-stream_loop","-1","-i",str(source),"-ss",f"{offset:.1f}","-t",str(cut),
                 "-vf",f"scale=760:1352:force_original_aspect_ratio=increase,crop=720:1280:(iw-ow)/2+{x}:(ih-oh)/2+{y},eq=contrast=1.05:saturation=1.10,fps=25",
                 "-an","-c:v","libx264","-preset","ultrafast","-crf","26","-threads","1",
                 "-pix_fmt","yuv420p","-movflags","+faststart",str(output)])
            normalized.append(output); job["progress"]=45+int((index+1)/count*30); write_job(job)
        (folder/"concat.txt").write_text("".join(f"file '{path.name}'\n" for path in normalized),"utf-8")
        (folder/"subs.ass").write_text(ass_subtitles(script,duration,alignment),"utf-8")
        run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(folder/"concat.txt"),"-i",str(folder/"voice.mp3"),
             "-vf",f"ass={folder/'subs.ass'}","-af","apad=pad_dur=0.65","-c:v","libx264","-preset","veryfast","-crf","26",
             "-threads","1","-pix_fmt","yuv420p","-c:a","aac","-b:a","128k",
             "-maxrate","2800k","-bufsize","5600k","-movflags","+faststart","-shortest",str(folder/"shorts.mp4")])
        job.update(state=1,progress=100,videos=[f"/files/{task_id}.mp4"],error=""); write_job(job)
    except Exception as exc:
        job.update(state=-1,error=f"{type(exc).__name__}: {str(exc)[:700]}"); write_job(job)
        # Preserve the small status JSON long enough for the editor to read the
        # error, but remove downloaded stock clips and rendered fragments.
        shutil.rmtree(folder,ignore_errors=True)
