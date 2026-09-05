from __future__ import annotations

import json

from ..channels import CHANNELS
from .models import ShortBrief, ShortScene


class ShortSceneService:
    def __init__(self, editor):
        self.editor = editor

    async def remix(self, brief: ShortBrief) -> list[ShortScene]:
        current = [
            {"seconds": scene.seconds, "visual": scene.visual, "screen_text": scene.screen_text, "asset_type": scene.asset_type}
            for scene in brief.scenes
        ]
        contract = (
            "Переподбери ТОЛЬКО визуалы для готового Shorts. Озвучку, хук, CTA, длительности сцен и экранный текст не меняй. "
            "Каждая сцена должна буквально поддерживать реплику, а не быть абстрактным красивым фоном. "
            "Допустимые asset_type: stock_video, brand_card, screenshot, meme, market_chart, text_scene, user_asset. "
            "Для Gifts избегай подарочных коробок, ювелирки и счастливых людей; нужны digital collectible, интерфейс, график, Telegram/TON-контекст. "
            "Для футбола не используй защищённые трансляции: тренировка, поле, тактическая доска, детали экипировки, раздевалка. "
            "Верни только JSON-массив объектов seconds, visual, screen_text, asset_type без markdown."
        )
        raw = await self.editor.llm(
            CHANNELS[brief.channel]["voice"],
            f"{contract}\n\nОЗВУЧКА:\n{brief.voiceover}\n\nТЕКУЩИЕ СЦЕНЫ:\n{json.dumps(current, ensure_ascii=False)}",
            .92,
        )
        text = (raw or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start, end = text.find("["), text.rfind("]")
        if start < 0 or end < start:
            raise ValueError("Shorts: модель не вернула массив сцен")
        data = json.loads(text[start:end + 1])
        if len(data) != len(brief.scenes):
            raise ValueError("Shorts: число сцен при замене кадров изменилось")
        result = []
        for old, value in zip(brief.scenes, data):
            scene = ShortScene.from_dict(value)
            # Timing and on-screen copy are immutable in a visual-only reroll.
            scene.seconds = old.seconds
            scene.screen_text = old.screen_text
            if not scene.visual:
                scene.visual = old.visual
            result.append(scene)
        return result
