import json
import os
import shutil
import subprocess
import threading
import uuid
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from ultralytics import YOLO
try:
    from .analytics import coach_notes, player_report
    from .visuals import COLOR_RU, jersey_color, player_wall
except ImportError:  # Railway root directory can be matchlens_service/
    from analytics import coach_notes, player_report
    from visuals import COLOR_RU, jersey_color, player_wall

DATA=Path(os.getenv("MATCHLENS_DATA_DIR","/data")); UPLOADS=DATA/"uploads"; JOBS=DATA/"jobs"; ARTIFACTS=DATA/"artifacts"
for folder in (UPLOADS,JOBS,ARTIFACTS): folder.mkdir(parents=True,exist_ok=True)
API_KEY=os.getenv("MATCHLENS_API_KEY","").strip(); MODEL=os.getenv("MATCHLENS_MODEL","yolo11n.pt")
app=FastAPI(title="MatchLens",version="0.1.0"); model=None; model_lock=threading.Lock()


@app.on_event("startup")
def recover_interrupted_jobs():
    """Background work cannot survive a Railway restart; never leave stale 5% jobs forever."""
    for path in JOBS.glob("*.json"):
        try:
            job=json.loads(path.read_text("utf-8"))
            if job.get("status") in {"queued","processing"}:
                job.update(status="failed",error="Worker перезапустился во время разбора. Запусти задание заново")
                write_job(job)
        except (OSError,ValueError,KeyError): continue


class MatchIn(BaseModel):
    source: dict
    target: dict
    mode: str="full"
    outputs: list[str]=Field(default_factory=list)


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
    authorize(x_api_key); job=read_job(job_id); job["tracker_id"]=payload.tracker_id; job["status"]="processing"; job["progress"]=75; job["error"]=None; write_job(job)
    background.add_task(build_report,job_id); return {"ok":True}


@app.get("/v1/reports/{job_id}",response_class=HTMLResponse)
def report(job_id:str):
    job=read_job(job_id); metrics=job.get("metrics",{}); target=metrics.get("selected_player",{})
    rows="".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k,v in target.items() if k not in {"zones_percent","burst_timestamps","coach_notes"}) or "<tr><td colspan=2>Выбери игрока по tracker_id</td></tr>"
    notes="".join(f"<li>{x}</li>" for x in target.get("coach_notes",[]))
    selection=f'<h2>Выбери игрока</h2><img src="/v1/artifacts/{job_id}/players.jpg"><p>Номер на рамке — tracker_id для команды /matchplayer</p>' if job.get("preview_ready") else ""
    media=f'<img src="/v1/artifacts/{job_id}/heatmap.png"><h2>Ключевые эпизоды</h2>'+"".join(f'<video controls preload="metadata" src="{url}"></video>' for url in job.get("clips",[])) if target else ""
    return f"<html><meta charset=utf-8><style>body{{background:#090d12;color:#eef;font:18px Arial;max-width:860px;margin:40px auto}}h1,h2{{color:#73ff9f}}table{{width:100%;border-collapse:collapse}}td{{padding:12px;border-bottom:1px solid #29313b}}img,video{{width:100%;border-radius:18px;margin:12px 0}}</style><h1>MatchLens · отчёт</h1><p>Статус: {job['status']}</p>{selection}<table>{rows}</table><ul>{notes}</ul>{media}</html>"


@app.get("/v1/artifacts/{job_id}/{name}")
def artifact(job_id:str,name:str):
    if name not in {"players.jpg","heatmap.png","clip-1.mp4","clip-2.mp4","clip-3.mp4"}: raise HTTPException(404,"artifact not found")
    path=ARTIFACTS/job_id/name
    if not path.exists(): raise HTTPException(404,"artifact not ready")
    return FileResponse(path)


def resolve_source(job):
    ref=str(job["source"].get("ref","") or job["source"].get("source_ref",""))
    if ref.startswith("upload:"): return UPLOADS/ref.split(":",1)[1]
    output=UPLOADS/f"{job['id']}.mp4"
    format_selector="worst[height>=480][height<=540]/worst[height>=480][height<=720]/best[height<=720]"
    subprocess.run(["yt-dlp","--no-playlist","--socket-timeout","30","--retries","3","--max-filesize","1500M",
                    "-f",format_selector,"-o",str(output),ref],check=True,timeout=1200)
    return output


def get_model():
    global model
    with model_lock:
        if model is None: model=YOLO(MODEL)
    return model


def requested_colour(job):
    value=str((job.get("target") or {}).get("player","")).lower()
    aliases={"white":("бел",),"black":("чёр","черн"),"gray":("сер",),"red":("красн",),
             "orange":("оранж",),"yellow":("жёлт","желт"),"green":("зелён","зелен"),
             "blue":("син",),"purple":("фиолет",),"pink":("розов",)}
    return next((colour for colour,words in aliases.items() if any(word in value for word in words)),None)


def analyse(job_id):
    job=read_job(job_id)
    try:
        job.update(status="processing",progress=5); write_job(job); video=resolve_source(job); cap=cv2.VideoCapture(str(video))
        fps=max(1.0,cap.get(cv2.CAP_PROP_FPS)); frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); duration=frames/fps; stride=max(1,int(fps/4)); tracks=defaultdict(list); balls=[]; index=0; best_crops={}
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
                    if box.id is not None:
                        track_id=int(box.id.item()); tracks[track_id].append((index/fps,cx,cy))
                        x1,y1,x2,y2=map(int,xy); x1=max(0,x1); y1=max(0,y1); x2=min(frame.shape[1],x2); y2=min(frame.shape[0],y2)
                        crop=frame[y1:y2,x1:x2]
                        if crop.size:
                            score=crop.shape[0]*crop.shape[1]
                            if score>best_crops.get(track_id,(0,None))[0]: best_crops[track_id]=(score,crop.copy())
            index+=1
            if index%(stride*80)==0: job["progress"]=min(65,5+int(index/max(1,frames)*60)); write_job(job)
        cap.release(); summary={}; raw={}
        ranked=sorted(tracks.items(),key=lambda item:len(item[1]),reverse=True)[:36]
        crops={track_id:value[1] for track_id,value in best_crops.items() if track_id in dict(ranked)}
        for track_id,points in ranked:
            report=player_report(points,duration); report["jersey_color"]=jersey_color(crops.get(track_id)); report["jersey_color_ru"]=COLOR_RU[report["jersey_color"]]
            summary[str(track_id)]=report; raw[str(track_id)]=points
        wanted=requested_colour(job)
        suggested=[track_id for track_id,report in summary.items()
                   if report.get("jersey_color")==wanted and report.get("confidence")!="low"][:8] if wanted else []
        (JOBS/f"{job_id}.tracks.json").write_text(json.dumps(raw),"utf-8")
        if crops:
            folder=ARTIFACTS/job_id; folder.mkdir(parents=True,exist_ok=True); player_wall(crops,summary,folder/"players.jpg"); job["preview_ready"]=True
        job["video_path"]=str(video)
        job["metrics"]={"duration_seconds":round(duration,1),"players":summary,"suggested_trackers":suggested,
                        "requested_colour":wanted,"ball_detections":len(balls),"sampling_fps":4,
                        "accuracy_note":"Координаты, цвет формы и движение оценены по кадру. Это не GPS и не официальный event-data"}
        job.update(status="awaiting_selection",progress=70,report_url=f"/v1/reports/{job_id}"); write_job(job)
    except Exception as exc:
        message=str(exc)[:400]
        if "честный разбор невозможен" in message:
            job.update(status="awaiting_selection",progress=70,error=message)
        else:
            job.update(status="failed",error=f"{type(exc).__name__}: {message}")
        write_job(job)


def build_report(job_id):
    job=read_job(job_id)
    try:
        players=job.get("metrics",{}).get("players",{}); selected=players.get(str(job.get("tracker_id")))
        if not selected: raise ValueError("Выбранный tracker_id не найден в матче")
        if selected.get("confidence")=="low" or float(selected.get("visible_seconds",0))<8:
            raise ValueError("Игрок виден меньше 8 секунд: честный разбор невозможен. Выбери другой ID или пришли более крупный эпизод")
        points=json.loads((JOBS/f"{job_id}.tracks.json").read_text("utf-8"))[str(job["tracker_id"])]
        folder=ARTIFACTS/job_id; folder.mkdir(parents=True,exist_ok=True); heatmap=np.zeros((720,1280),dtype=np.uint8)
        for _,x,y in points: cv2.circle(heatmap,(int(x*1279),int(y*719)),35,16,-1)
        heatmap=cv2.GaussianBlur(heatmap,(0,0),35); heatmap=cv2.applyColorMap(cv2.normalize(heatmap,None,0,255,cv2.NORM_MINMAX),cv2.COLORMAP_TURBO); cv2.imwrite(str(folder/"heatmap.png"),heatmap)
        clips=[]
        for number,timestamp in enumerate(selected.get("burst_timestamps",[])[:3],1):
            output=folder/f"clip-{number}.mp4"; start=max(0,float(timestamp)-4)
            process=subprocess.run(["ffmpeg","-y","-ss",str(start),"-i",job["video_path"],"-t","8","-c:v","libx264","-preset","veryfast","-c:a","aac",str(output)],capture_output=True)
            if process.returncode==0: clips.append(f"/v1/artifacts/{job_id}/clip-{number}.mp4")
        job["clips"]=clips; job["metrics"]["selected_player"]={"tracker_id":job["tracker_id"],**selected,"coach_notes":coach_notes(selected)}; job.update(status="completed",progress=100,report_url=f"/v1/reports/{job_id}",error=None); write_job(job)
    except Exception as exc:
        job.update(status="failed",error=f"{type(exc).__name__}: {str(exc)[:400]}"); write_job(job)
