from __future__ import annotations

import asyncio
import json
import math
import os
import subprocess
import uuid
from pathlib import Path

import aiohttp
import edge_tts
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

try:
    from .core import ass_subtitles, clean_script, unique_terms
except ImportError:
    from core import ass_subtitles, clean_script, unique_terms

DATA=Path(os.getenv("SHORTS_DATA_DIR","/data")); JOBS=DATA/"jobs"; TASKS=DATA/"tasks"
for folder in (JOBS,TASKS): folder.mkdir(parents=True,exist_ok=True)
API_KEY=os.getenv("SHORTS_API_KEY","").strip(); PEXELS_KEY=os.getenv("PEXELS_API_KEY","").strip()
app=FastAPI(title="Content OS Shorts Worker",version="1.0")


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
def health(): return {"ok":True,"service":"content-os-shorts","pexels":bool(PEXELS_KEY),"persistent":str(DATA)=="/data"}


@app.post("/api/v1/videos")
def create(payload:dict,background:BackgroundTasks,x_api_key:str|None=Header(None)):
    authorize(x_api_key); task_id=str(uuid.uuid4()); folder=TASKS/task_id; folder.mkdir(parents=True,exist_ok=True)
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
    return FileResponse(path,media_type="video/mp4",filename=f"shorts-{task_id}.mp4")


async def pexels_clips(terms:list[str],folder:Path,limit=6)->list[Path]:
    if not PEXELS_KEY: raise RuntimeError("PEXELS_API_KEY не задан в Shorts Worker")
    urls=[]; headers={"Authorization":PEXELS_KEY}
    async with aiohttp.ClientSession(headers=headers,timeout=aiohttp.ClientTimeout(total=90)) as session:
        for term in terms:
            async with session.get("https://api.pexels.com/videos/search",params={"query":term,"per_page":8,"orientation":"portrait"}) as response:
                if response.status>=400: continue
                for video in (await response.json()).get("videos",[]):
                    files=video.get("video_files") or []
                    vertical=[x for x in files if int(x.get("height") or 0)>int(x.get("width") or 0) and int(x.get("width") or 0)>=540]
                    candidates=vertical or files
                    if candidates:
                        choice=min(candidates,key=lambda x:abs(int(x.get("width") or 720)-720)); url=choice.get("link")
                        if url and url not in urls: urls.append(url)
                    if len(urls)>=limit: break
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
    if result.returncode: raise RuntimeError((result.stderr or result.stdout)[-900:])


async def render(task_id:str,payload:dict):
    job=read_job(task_id); folder=TASKS/task_id
    try:
        script=clean_script(payload.get("video_script") or payload.get("video_subject") or "")
        if len(script)<30: raise RuntimeError("Сценарий озвучки слишком короткий")
        job["progress"]=5; write_job(job)
        voice=str(payload.get("voice_name") or "ru-RU-DmitryNeural")
        await edge_tts.Communicate(script,voice=voice,rate="+10%").save(str(folder/"voice.mp3"))
        probe=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(folder/"voice.mp3")],text=True)
        duration=max(8.0,float(probe.strip())); job["progress"]=20; write_job(job)
        clips=await pexels_clips(unique_terms(payload),folder)
        if len(clips)<3: raise RuntimeError("Pexels вернул меньше трёх пригодных видеоклипов")
        job["progress"]=45; write_job(job); part_duration=math.ceil(duration/len(clips))+1; normalized=[]
        for index,source in enumerate(clips):
            output=folder/f"part-{index}.mp4"
            run(["ffmpeg","-y","-stream_loop","-1","-i",str(source),"-t",str(part_duration),"-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30","-an","-c:v","libx264","-preset","veryfast","-crf","24",str(output)])
            normalized.append(output); job["progress"]=45+int((index+1)/len(clips)*30); write_job(job)
        (folder/"concat.txt").write_text("".join(f"file '{path.name}'\n" for path in normalized),"utf-8")
        (folder/"subs.ass").write_text(ass_subtitles(script,duration),"utf-8")
        run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(folder/"concat.txt"),"-i",str(folder/"voice.mp3"),"-vf",f"ass={folder/'subs.ass'}","-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-b:a","160k","-movflags","+faststart","-shortest",str(folder/"shorts.mp4")])
        job.update(state=1,progress=100,videos=[f"/files/{task_id}.mp4"],error=""); write_job(job)
    except Exception as exc:
        job.update(state=-1,error=f"{type(exc).__name__}: {str(exc)[:700]}"); write_job(job)
