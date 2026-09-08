from __future__ import annotations

import hashlib
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
        try:
            data = self._parse_scenes(raw)
            if len(data) != len(brief.scenes):
                raise ValueError("scene count changed")
        except (ValueError, TypeError, json.JSONDecodeError):
            # Visual rerolls are an operator convenience, not a release gate. LLMs
            # occasionally wrap the array in an object or return prose/truncated
            # JSON. A deterministic reroll is always better than a dead button.
            return self._fallback_remix(brief)
        result = []
        for old, value in zip(brief.scenes, data):
            if not isinstance(value, dict):
                return self._fallback_remix(brief)
            scene = ShortScene.from_dict(value)
            # Timing and on-screen copy are immutable in a visual-only reroll.
            scene.seconds = old.seconds
            scene.screen_text = old.screen_text
            if not scene.visual:
                scene.visual = old.visual
            result.append(scene)
        return result

    @staticmethod
    def _parse_scenes(raw: str) -> list[dict]:
        text = (raw or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        decoder = json.JSONDecoder()
        # Accept the documented array as well as frequent {"scenes": [...]} and
        # {"data": {"scenes": [...]}} wrappers without another model request.
        for index, char in enumerate(text):
            if char not in "[{":
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for key in ("scenes", "items", "result"):
                    nested = value.get(key)
                    if isinstance(nested, list):
                        return nested
                    if isinstance(nested, dict) and isinstance(nested.get("scenes"), list):
                        return nested["scenes"]
        raise ValueError("Shorts: модель не вернула массив сцен")

    @staticmethod
    def _fallback_remix(brief: ShortBrief) -> list[ShortScene]:
        banks = {
            "gifts": (
                "smartphone crypto marketplace close up vertical", "digital collectible rotating 3d dark studio",
                "finger scrolling market listings vertical", "price chart neon screen macro",
                "collector inspecting digital rarity interface", "telegram marketplace phone over shoulder",
                "abstract liquidity flow 3d animation", "magnifying glass over collectible details 3d",
                "empty shopping cart dark 3d", "market alert notification phone vertical",
                "vault opening with digital token 3d", "decision crossroads dark cinematic vertical",
            ),
            "liga": (
                "football boots first touch close up vertical", "player scanning field before pass vertical",
                "tactical board magnets close up", "solo football sprint training vertical",
                "goalkeeper reaction drill close up", "empty stadium tunnel cinematic vertical",
                "football cone footwork drill vertical", "coach pointing tactical movement vertical",
                "ball spin slow motion grass vertical", "athlete recovery breath close up vertical",
                "training bibs locker room cinematic", "floodlights football pitch night vertical",
            ),
        }
        bank = banks.get(brief.channel, banks["liga"])
        signature = "|".join(scene.visual for scene in brief.scenes).encode("utf-8")
        shift = int(hashlib.sha256(signature).hexdigest()[:8], 16) % len(bank)
        result = []
        for index, old in enumerate(brief.scenes):
            visual = bank[(shift + index) % len(bank)]
            if visual.casefold() == old.visual.casefold():
                visual = bank[(shift + index + 1) % len(bank)]
            # Two branded 3D cards break up stock footage; the worker injects the
            # current draft card as an inline asset before rendering.
            asset_type = "brand_card" if index in {0, len(brief.scenes) - 2} else "stock_video"
            result.append(ShortScene(old.seconds, visual, old.screen_text, asset_type))
        return result
