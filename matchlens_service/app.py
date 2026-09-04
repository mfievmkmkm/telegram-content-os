import json
import os
import shutil
import subprocess
import threading
import uuid
from collections import defaultdict
from pathlib import Path

import cv2
from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from ultralytics import YOLO

DATA=Path(os.getenv("MATCHLENS_DATA_DIR","/data")); UPLOADS=DATA/"uploads"; JOBS=DATA/"jobs"
for folder in (UPLOADS,JOBS): folder.mkdir(parents=True,exist_ok=True)
API_KEY=os.getenv("MATCHLENS_API_KEY","").strip(); MODEL=os.getenv("MATCHLENS_MODEL","yolo11n.pt")
app=FastAPI(title="MatchLens",version="0.1.0"); model=None; model_lock=threading.Lock()


class MatchIn(BaseModel):
    source: dict
    target: dict
    mode: str="full"
    outputs: list[str]=[]


class TargetIn(BaseModel): tracker_id: int


def authorize(value):
    if API_KEY and value!=API_KEY: raise HTTPException(401,"invalid api key")


def path_for(job_id): return JOBS/f"{job_id}.json"
def read_job(job_id):
    path=path_for(job_id)
    if not path.exists(): raise HTTPException(404,f"{job_id}: task not found")
    return json.loads(path.read_text("utf-8"))
def write_job(job):
    temp=path_for(job["id"]).with_suffix(".tmp"); temp.write_text(json.dumps(job,ensure_ascii=False),"utf-8"); temp.replace(path_for(job["id"]))


@app.get("/health")
def health(): return {"ok":True,"service":"matchlens","model":MODEL}


@app.post("/v1/uploads")
def upload(file:UploadFile=File(...),x_api_key:str|None=Header(None)):
    authorize(x_api_key); suffix=Path(file.filename or "video.mp4").suffix or ".mp4"; ref=f"upload:{uuid.uuid4()}{suffix}"
    with (UPLOADS/ref.split(":",1)[1]).open("wb") as target: shutil.copyfileobj(file.file,target)
    return {"ref":ref}


@app.post("/v1/matches")
def submit(payload:MatchIn,background:BackgroundTasks,x_api_key:str|None=Header(None)):
    authorize(x_api_key); job_id=str(uuid.uuid4()); job={"id":job_id,"status":"queued","progress":0,"source":payload.source,"target":payload.target,"mode":payload.mode}
    write_job(job); background.add_task(analyse,job_id); return {"id":job_id,"status":"queued"}


@app.get("/v1/matches/{job_id}")
def status(job_id:str,x_api_key:str|None=Header(None)):
    authorize(x_api_key); return read_job(job_id)


@app.post("/v1/matches/{job_id}/target")
def target(job_id:str,payload:TargetIn,background:BackgroundTasks,x_api_key:str|None=Header(None)):
    authorize(x_api_key); job=read_job(job_id); job["tracker_id"]=payload.tracker_id; job["status"]="processing"; job["progress"]=75; write_job(job)
    background.add_task(build_report,job_id); return {"ok":True}


@app.get("/v1/reports/{job_id}",response_class=HTMLResponse)
def report(job_id:str):
    job=read_job(job_id); metrics=job.get("metrics",{}); target=metrics.get("selected_player",{})
    rows="".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k,v in target.items()) or "<tr><td colspan=2>Выбери игрока по tracker_id</td></tr>"
    return f"<html><meta charset=utf-8><style>body{{background:#090d12;color:#eef;font:18px Arial;max-width:760px;margin:40px auto}}h1{{color:#73ff9f}}table{{width:100%;border-collapse:collapse}}td{{padding:12px;border-bottom:1px solid #29313b}}</style><h1>MatchLens · отчёт</h1><p>Статус: {job['status']}</p><table>{rows}</table></html>"


def resolve_source(job):
    ref=str(job["source"].get("ref","") or job["source"].get("source_ref",""))
    if ref.startswith("upload:"): return UPLOADS/ref.split(":",1)[1]
    output=UPLOADS/f"{job['id']}.mp4"
    subprocess.run(["yt-dlp","-f","best[height<=720]","-o",str(output),ref],check=True,timeout=900)
    return output


def get_model():
    global model
    with model_lock:
        if model is None: model=YOLO(MODEL)
    return model


def analyse(job_id):
    job=read_job(job_id)
    try:
        job.update(status="processing",progress=5); write_job(job); video=resolve_source(job); cap=cv2.VideoCapture(str(video))
        fps=max(1.0,cap.get(cv2.CAP_PROP_FPS)); frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); duration=frames/fps; stride=max(1,int(fps/4)); tracks=defaultdict(list); balls=[]; index=0
        detector=get_model()
        while True:
            ok,frame=cap.read()
            if not ok: break
            if index%stride: index+=1; continue
            result=detector.track(frame,persist=True,tracker="bytetrack.yaml",classes=[0,32],verbose=False,imgsz=640)[0]
            if result.boxes is not None:
                for box in result.boxes:
                    cls=int(box.cls.item()); xy=box.xyxy[0].tolist(); cx=(xy[0]+xy[2])/2/frame.shape[1]; cy=(xy[1]+xy[3])/2/frame.shape[0]
                    if cls==32: balls.append((index/fps,cx,cy)); continue
                    if box.id is not None: tracks[int(box.id.item())].append((index/fps,cx,cy))
            index+=1
            if index%(stride*80)==0: job["progress"]=min(65,5+int(index/max(1,frames)*60)); write_job(job)
        cap.release(); summary={}
        for track_id,points in tracks.items():
            distance=sum(((a[1]-b[1])**2+(a[2]-b[2])**2)**.5 for a,b in zip(points,points[1:]))
            summary[str(track_id)]={"visible_seconds":round(len(points)/4,1),"movement_index":round(distance*100,1),"average_x":round(sum(p[1] for p in points)/len(points),3),"average_y":round(sum(p[2] for p in points)/len(points),3)}
        job["metrics"]={"duration_seconds":round(duration,1),"players":summary,"ball_detections":len(balls),"sampling_fps":4,"accuracy_note":"Координаты и движение оценены по кадру; это не GPS-метрики"}
        job.update(status="awaiting_selection",progress=70,report_url=f"/v1/reports/{job_id}"); write_job(job)
    except Exception as exc:
        job.update(status="failed",error=f"{type(exc).__name__}: {str(exc)[:400]}"); write_job(job)


def build_report(job_id):
    job=read_job(job_id); players=job.get("metrics",{}).get("players",{}); selected=players.get(str(job.get("tracker_id")))
    if not selected: job.update(status="failed",error="Выбранный tracker_id не найден в матче"); write_job(job); return
    job["metrics"]["selected_player"]={"tracker_id":job["tracker_id"],**selected}; job.update(status="completed",progress=100,report_url=f"/v1/reports/{job_id}"); write_job(job)
