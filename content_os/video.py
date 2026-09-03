import json

import aiohttp

from .channels import CHANNELS

SHORTS_RULES = """Создай производственное задание для вертикального ролика 9:16 на 30–42 секунды.
Первая фраза должна остановить скролл за 2 секунды: боль, конфликт, абсурд или опасное заблуждение.
Никаких приветствий. Озвучка — 75–105 слов, разговорный русский, без пустых фраз.
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
        except (json.JSONDecodeError,ValueError):
            repaired=await self.editor.llm(
                "Ты JSON-валидатор. Исправь синтаксис и верни только один JSON-объект без markdown.",
                raw,
                .1,
            )
            data=self.parse_json(repaired)
        self.validate(data)
        data.update({"draft_id":draft["id"],"channel":draft["channel_key"],"aspect_ratio":"9:16","language":"ru"})
        payload=json.dumps(data,ensure_ascii=False,indent=2); job_id=self.db.save_video_job(draft["id"],payload)
        delivered=False
        if self.settings.mpt_webhook_url:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(self.settings.mpt_webhook_url,json=data) as response:
                    if response.status>=400: raise RuntimeError(f"MoneyPrinterTurbo adapter HTTP {response.status}")
                    delivered=True
        return job_id,data,payload,delivered

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
