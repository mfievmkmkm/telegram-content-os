from dataclasses import dataclass
import os
import tempfile
from urllib.parse import urlparse

import aiohttp


@dataclass(frozen=True)
class MatchRequest:
    source_type: str
    source_ref: str
    player_ref: str
    analysis_mode: str = "full"

    def validate(self):
        if self.source_type not in {"url", "telegram"}:
            raise ValueError("Неподдерживаемый источник матча")
        if self.analysis_mode not in {"player", "team", "full"}:
            raise ValueError("Неподдерживаемый режим анализа")
        if self.source_type == "url":
            parsed=urlparse(self.source_ref)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("Нужна полная ссылка на видео")
        if not self.player_ref.strip():
            raise ValueError("Нужно указать игрока или команду")


class MatchLensClient:
    def __init__(self,settings,db):
        self.base_url=settings.matchlens_base_url
        self.api_key=settings.matchlens_api_key
        self.timeout=settings.matchlens_timeout_minutes*60
        self.upload_max_mb=getattr(settings,"matchlens_upload_max_mb",100)
        self.db=db

    @property
    def ready(self):
        return bool(self.base_url)

    async def submit(self,request:MatchRequest):
        request.validate()
        local_id=self.db.save_match_job(request.source_type,request.source_ref,request.player_ref,request.analysis_mode)
        if not self.ready:
            return local_id,None
        headers={"x-api-key":self.api_key} if self.api_key else {}
        payload={"source":{"type":request.source_type,"ref":request.source_ref},
                 "target":{"player":request.player_ref},"mode":request.analysis_mode,
                 "outputs":["annotated_video","radar","player_stats","clips","coach_report"]}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(f"{self.base_url}/v1/matches",json=payload,headers=headers) as response:
                    response.raise_for_status(); data=await response.json()
            external=str(data.get("id") or data.get("job_id") or "")
            if not external: raise RuntimeError("MatchLens не вернул ID задания")
            self.db.update_match_job(local_id,external_id=external,status="processing")
            return local_id,external
        except Exception as exc:
            self.db.update_match_job(local_id,status="failed",error=str(exc)[:500])
            raise

    async def refresh(self,local_id:int):
        row=self.db.match_job(local_id)
        if not row: raise ValueError("Разбор не найден")
        external=row["external_id"]
        if not external or not self.ready: return row
        headers={"x-api-key":self.api_key} if self.api_key else {}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(f"{self.base_url}/v1/matches/{external}",headers=headers) as response:
                response.raise_for_status(); data=await response.json()
        status=str(data.get("status","processing")); progress=max(0,min(100,int(data.get("progress",0))))
        result=data.get("report_url") or data.get("result_url")
        import json
        metrics=json.dumps(data.get("metrics"),ensure_ascii=False) if data.get("metrics") else None
        self.db.update_match_job(local_id,status=status,progress=progress,result_url=result,error=data.get("error"),metrics_json=metrics)
        return self.db.match_job(local_id)

    async def select_target(self,local_id:int,tracker_id:int):
        row=self.db.match_job(local_id)
        if not row: raise ValueError("Разбор не найден")
        if not row["external_id"] or not self.ready: raise ValueError("Видеосервис ещё не подключён")
        headers={"x-api-key":self.api_key} if self.api_key else {}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(f"{self.base_url}/v1/matches/{row['external_id']}/target",json={"tracker_id":tracker_id},headers=headers) as response:
                response.raise_for_status()
        self.db.update_match_job(local_id,status="processing",progress=70,error=None)
        return self.db.match_job(local_id)

    async def upload_telegram(self,bot,file_id:str,file_size:int=0):
        if not self.ready: raise RuntimeError("Видеосервис MatchLens ещё не подключён")
        if file_size and file_size>self.upload_max_mb*1024*1024:
            raise ValueError(f"Файл больше {self.upload_max_mb} МБ. Для полного матча пришли ссылку на облако или YouTube.")
        temp_path=""
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4",delete=False) as temporary: temp_path=temporary.name
            telegram_file=await bot.get_file(file_id); await bot.download_file(telegram_file.file_path,temp_path)
            headers={"x-api-key":self.api_key} if self.api_key else {}; form=aiohttp.FormData()
            with open(temp_path,"rb") as video:
                form.add_field("file",video,filename="telegram.mp4",content_type="video/mp4")
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
                    async with session.post(f"{self.base_url}/v1/uploads",data=form,headers=headers) as response:
                        body=await response.json(content_type=None)
                        if response.status>=400: raise RuntimeError(body.get("detail") or f"Upload HTTP {response.status}")
            return str(body["ref"])
        finally:
            if temp_path: os.unlink(temp_path)


def confidence_legend():
    return ("<b>Точность отчёта</b>\n"
            "✅ Измерено — событие уверенно видно\n"
            "≈ Оценено — рассчитано по координатам видео\n"
            "◌ Не видно — игрок или мяч отсутствовал в кадре")
