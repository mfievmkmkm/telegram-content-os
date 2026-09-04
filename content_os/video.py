import asyncio
import json
import re
from urllib.parse import urljoin

import aiohttp

from .channels import CHANNELS
from .formatting import plain_text

SHORTS_RULES = """Создай производственное задание для вертикального ролика 9:16 на 25–36 секунд.
Первая фраза должна остановить скролл за 2 секунды: боль, конфликт, абсурд или опасное заблуждение.
Никаких приветствий. Озвучка — 60–80 слов, разговорный русский, без пустых фраз.
Каждые 2–5 секунд меняется визуальный акцент. Крупный экранный текст — максимум 6 слов.
Для футбола не проси кадры защищённых трансляций: тренировка, поле, раздевалка, схемы, силуэты.
Для Gifts используй интерфейсные макеты, подарки, графики, TON и тёмный неон; не выдумывай цены.
Верни СТРОГО JSON без markdown:
{"title":"...","hook":"...","voiceover":"...","scenes":[{"seconds":4,"visual":"English stock footage query or exact edit instruction","screen_text":"..."}],"caption":"...","music_mood":"...","cta":"..."}
"""


class VideoFactory:
    def __init__(self, settings, database, editor): self.settings,self.db,self.editor=settings,database,editor

    async def create(self, draft):
        raw=await self.editor.llm(CHANNELS[draft["channel_key"]]["voice"],f"{SHORTS_RULES}\n\nПОСТ:\n{draft['text']}",.95)
        try:
            data=self.parse_json(raw)
            self.validate(data)
        except (json.JSONDecodeError,ValueError,TypeError):
            try:
                repaired=await self.editor.llm(
                    "Ты JSON-валидатор. Заполни ВСЕ обязательные поля title, hook, voiceover, scenes, caption, music_mood, cta. "
                    "scenes — массив из 5–10 объектов seconds, visual, screen_text. Верни только JSON без markdown.",
                    f"{SHORTS_RULES}\n\nИСХОДНЫЙ ОТВЕТ:\n{raw}\n\nПОСТ:\n{draft['text']}",
                    .1,
                )
                data=self.parse_json(repaired); self.validate(data)
            except (json.JSONDecodeError,ValueError,TypeError):
                data=self.fallback(draft)
        data.update({"draft_id":draft["id"],"channel":draft["channel_key"],"aspect_ratio":"9:16","language":"ru"})
        payload=json.dumps(data,ensure_ascii=False,indent=2); job_id=self.db.save_video_job(draft["id"],payload)
        delivered=False
        if self.settings.mpt_webhook_url:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(self.settings.mpt_webhook_url,json=data) as response:
                    if response.status>=400: raise RuntimeError(f"Shorts webhook HTTP {response.status}")
                    delivered=True
        return job_id,data,payload,delivered

    async def render(self,data,progress=None):
        """Submit a production job to a compatible persistent Shorts Worker."""
        if not self.settings.mpt_base_url:
            raise RuntimeError("Shorts Worker ещё не подключён")
        headers={"x-api-key":self.settings.mpt_api_key} if self.settings.mpt_api_key else {}
        body=self.mpt_payload(data)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90),headers=headers) as session:
            created=await self._request_json(session,"POST","/api/v1/videos",json=body)
            task_id=str(self._data(created).get("task_id","")).strip()
            if not task_id: raise RuntimeError("Shorts Worker не вернул task_id")
            deadline=asyncio.get_running_loop().time()+self.settings.mpt_timeout_minutes*60
            last_progress=-1
            while asyncio.get_running_loop().time()<deadline:
                await asyncio.sleep(8)
                try:
                    status=self._data(await self._request_json(session,"GET",f"/api/v1/tasks/{task_id}"))
                except (aiohttp.ClientError,asyncio.TimeoutError,RuntimeError) as exc:
                    if "task not found" in str(exc).lower():
                        raise RuntimeError("Shorts Worker перезапустился во время склейки и потерял задачу. Проверь память сервиса и запусти Shorts заново") from exc
                    if self.transient_status_error(exc):
                        if progress and last_progress<5:
                            await progress(5); last_progress=5
                        await asyncio.sleep(12); continue
                    raise
                current=int(status.get("progress",0) or 0)
                if progress and current!=last_progress:
                    await progress(current); last_progress=current
                state=int(status.get("state",0) or 0)
                if state<0:
                    error=str(status.get("error") or "рендер завершился с ошибкой")[:500]
                    if "combined-1.mp4" in error or "FileNotFoundError" in error:
                        raise RuntimeError("Shorts Worker не получил видеоклипы от Pexels. Проверь PEXELS_API_KEY и его логи")
                    raise RuntimeError(error)
                output=status.get("videos") or status.get("combined_videos") or []
                if state==1 and output:
                    video_url=urljoin(self.settings.mpt_base_url+"/",str(output[0]).lstrip("/"))
                    async with session.get(video_url) as response:
                        if response.status>=400: raise RuntimeError(f"скачивание MP4: HTTP {response.status}")
                        content=await response.read()
                        if len(content)>49*1024*1024: raise RuntimeError("готовое видео больше лимита Telegram 49 МБ")
                        return task_id,content
            raise RuntimeError(f"рендер не завершился за {self.settings.mpt_timeout_minutes} минут")

    def mpt_payload(self,data):
        broad={
          "liga":["football training","soccer field","athlete running","football boots","sports coaching"],
          "gifts":["smartphone technology","digital art","financial chart","neon abstract","online marketplace"],
        }
        suggested=[str(scene.get("visual","")).strip() for scene in data["scenes"] if scene.get("visual")]
        terms=[]
        for term in broad.get(data.get("channel"),broad["liga"])+suggested[:2]:
            if term and term.lower() not in {item.lower() for item in terms}: terms.append(term)
        return {
            "video_subject":data["title"], "video_script":self.voice_script(data["voiceover"]),
            "video_terms":terms[:7], "video_aspect":"9:16", "video_source":"pexels",
            "video_concat_mode":"random", "video_transition_mode":"None", "video_clip_duration":4, "video_count":1,
            "voice_name":self.settings.mpt_voice_name, "voice_rate":1.13, "subtitle_enabled":True,
            "subtitle_position":"custom", "custom_position":76.0,
            "font_name":"DejaVuSans-Bold.ttf", "font_size":52,
            "text_fore_color":"#FFFFFF", "text_background_color":"#000000",
            "stroke_color":"#000000", "stroke_width":2.0, "paragraph_number":1,
            "video_language":"ru-RU", "n_threads":2,
            "bgm_type":"random", "bgm_volume":0.12, "voice_volume":1.0,
        }

    @staticmethod
    def voice_script(value):
        """Give neural TTS natural phrasing without dramatic synthetic pauses."""
        text=plain_text(str(value or ""))
        text=re.sub(r"[\r\n]+"," ",text)
        text=text.replace("—",",").replace("–",",")
        text=re.sub(r"\.{2,}",".",text)
        text=re.sub(r"\s*[,;:]\s*",", ",text)
        text=re.sub(r",(?:\s*,)+",",",text)
        return re.sub(r"\s{2,}"," ",text).strip(" ,")

    async def _request_json(self,session,method,path,**kwargs):
        async with session.request(method,self.settings.mpt_base_url+path,**kwargs) as response:
            body=await response.text()
            if response.status>=400: raise RuntimeError(f"Shorts Worker HTTP {response.status}: {body[:240]}")
            return json.loads(body)

    @staticmethod
    def _data(response):
        return response.get("data",response) if isinstance(response,dict) else {}

    @staticmethod
    def transient_status_error(exc):
        if isinstance(exc,(aiohttp.ClientError,asyncio.TimeoutError)): return True
        text=str(exc).lower()
        return any(marker in text for marker in ("http 502","http 503","http 504","failed to respond","connection reset"))

    @staticmethod
    def parse_json(raw):
        text=(raw or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start,end=text.find("{"),text.rfind("}")
        if start<0 or end<start: raise ValueError("Shorts: модель не вернула JSON")
        return json.loads(text[start:end+1])

    @staticmethod
    def validate(data):
        required={"title","hook","voiceover","scenes","caption","music_mood","cta"}
        missing=required-set(data)
        if missing: raise ValueError(f"Shorts JSON: нет полей {', '.join(sorted(missing))}")
        if not isinstance(data["scenes"],list) or not 5<=len(data["scenes"])<=10: raise ValueError("Shorts должен содержать 5–10 сцен")
        duration=sum(int(scene.get("seconds",0)) for scene in data["scenes"])
        if not 25<=duration<=48: raise ValueError(f"Некорректная длительность: {duration} сек")

    @staticmethod
    def fallback(draft):
        """Deterministic production brief when an LLM ignores the JSON contract."""
        text=plain_text(draft.get("text","")).strip()
        lines=[line.strip() for line in text.splitlines() if line.strip()]
        hook=(lines[0] if lines else "Остановись: здесь есть деталь, которую все пропускают")[:120]
        words=text.split(); voiceover=" ".join(words[:80])
        if len(voiceover.split())<35:
            voiceover=(voiceover+" Главное — не верить первому впечатлению. Посмотри на причину, проверь факты и только потом делай вывод.").strip()
        if draft.get("channel_key")=="gifts":
            visuals=["telegram gift dark neon","digital collectible close up","crypto market chart dark","phone marketplace scrolling","ton coin animation","collector decision concept","dark neon question mark"]
            mood="dark electronic tension"
        else:
            visuals=["football player training alone","football boots close up","soccer tactical board","player sprint training","empty stadium tunnel","coach observing practice","football field sunset"]
            mood="energetic sports tension"
        scenes=[{"seconds":5,"visual":visual,"screen_text":([hook,"Смотри глубже","Вот где ошибка","Решает деталь","Без оправданий","Проверь себя","А ты согласен?"][i])[:45]} for i,visual in enumerate(visuals)]
        return {"title":hook[:70],"hook":hook,"voiceover":voiceover,"scenes":scenes,
                "caption":text[:900],"music_mood":mood,"cta":lines[-1][:120] if lines else "А ты согласен?"}
