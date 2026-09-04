from __future__ import annotations

import math

import cv2
import numpy as np


COLOR_RU={"white":"белая","black":"чёрная","gray":"серая","red":"красная","orange":"оранжевая",
          "yellow":"жёлтая","green":"зелёная","blue":"синяя","purple":"фиолетовая","pink":"розовая","unknown":"не определён"}


def jersey_color(crop: np.ndarray) -> str:
    """Estimate a shirt colour from the torso, avoiding most grass/background."""
    if crop is None or crop.size==0 or crop.shape[0]<12 or crop.shape[1]<8: return "unknown"
    h,w=crop.shape[:2]; torso=crop[int(h*.18):max(int(h*.62),int(h*.18)+1),int(w*.20):max(int(w*.80),int(w*.20)+1)]
    hsv=cv2.cvtColor(torso,cv2.COLOR_BGR2HSV).reshape(-1,3)
    if not len(hsv): return "unknown"
    sat=float(np.median(hsv[:,1])); val=float(np.median(hsv[:,2]))
    if val<55: return "black"
    if sat<38: return "white" if val>175 else "gray"
    vivid=hsv[(hsv[:,1]>55)&(hsv[:,2]>45)]
    if not len(vivid): return "unknown"
    hue=float(np.median(vivid[:,0]))
    if hue<9 or hue>=172: return "red"
    if hue<20: return "orange"
    if hue<35: return "yellow"
    if hue<84: return "green"
    if hue<130: return "blue"
    if hue<158: return "purple"
    return "pink"


def player_wall(crops: dict[int, np.ndarray],reports: dict[str,dict],output,limit: int=24) -> None:
    ids=sorted(crops,key=lambda value: reports.get(str(value),{}).get("visibility_percent",0),reverse=True)[:limit]
    cols=4; tile_w,tile_h=320,390; rows=max(1,math.ceil(len(ids)/cols)); canvas=np.full((rows*tile_h,cols*tile_w,3),(9,13,18),np.uint8)
    for index,track_id in enumerate(ids):
        crop=crops[track_id]; y=(index//cols)*tile_h; x=(index%cols)*tile_w
        area_h,area_w=285,280; scale=min(area_w/crop.shape[1],area_h/crop.shape[0]); resized=cv2.resize(crop,(max(1,int(crop.shape[1]*scale)),max(1,int(crop.shape[0]*scale))))
        py=y+20+(area_h-resized.shape[0])//2; px=x+20+(area_w-resized.shape[1])//2; canvas[py:py+resized.shape[0],px:px+resized.shape[1]]=resized
        report=reports.get(str(track_id),{}); colour=str(report.get("jersey_color","unknown")).upper(); visible=report.get("visibility_percent",0)
        cv2.rectangle(canvas,(x+12,y+12),(x+308,y+378),(70,255,145),2)
        cv2.putText(canvas,f"ID {track_id}",(x+24,y+330),cv2.FONT_HERSHEY_SIMPLEX,1.05,(245,248,250),3,cv2.LINE_AA)
        cv2.putText(canvas,f"{colour}  |  visible {visible}%",(x+24,y+365),cv2.FONT_HERSHEY_SIMPLEX,.48,(70,255,145),1,cv2.LINE_AA)
    cv2.imwrite(str(output),canvas)
