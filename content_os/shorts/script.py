from __future__ import annotations

import json

from ..channels import CHANNELS
from ..formatting import plain_text
from .models import ShortBrief
from .presets import delivery


SCRIPT_CONTRACT = """Создай сценарий вертикального ролика 9:16.
Сначала качество текста, монтаж будет только после подтверждения редактором.
Хук обязан остановить скролл за первые 2 секунды: конкретная боль, конфликт, неожиданность или опасное заблуждение.
Никаких приветствий и AI-канцелярита. Каждое предложение короткое и произносимое вслух.
Не пересказывай исходный пост по абзацам: найди одну сильную мысль и преврати её в живой монолог.
Не придумывай цены, статистику, цитаты или события.
Верни СТРОГО JSON без markdown:
{"title":"...","hook":"...","voiceover":"...","scenes":[{"seconds":4,"visual":"English visual intent","screen_text":"...","asset_type":"stock_video"}],"caption":"...","music_mood":"...","cta":"..."}
asset_type может быть stock_video, brand_card, screenshot, meme, market_chart, text_scene или user_asset.
"""


class ShortScriptService:
    def __init__(self, editor):
        self.editor = editor

    async def prepare(self, draft, delivery_key: str = "punchy") -> ShortBrief:
        preset = delivery(delivery_key)
        prompt = (
            f"{SCRIPT_CONTRACT}\nПОДАЧА: {preset.title}. {preset.instruction}\n"
            f"Озвучка: {preset.target_words[0]}–{preset.target_words[1]} слов.\n"
            f"КАНАЛ: {draft['channel_key']}\n\nИСХОДНЫЙ МАТЕРИАЛ:\n{draft['text']}"
        )
        raw = await self.editor.llm(CHANNELS[draft["channel_key"]]["voice"], prompt, .9)
        data = self._parse(raw)
        data.update(channel=draft["channel_key"], draft_id=draft["id"])
        brief = ShortBrief.from_legacy(data)
        brief.delivery_preset = delivery_key
        self.validate(brief)
        return brief

    async def rewrite(self, brief: ShortBrief, mode: str) -> ShortBrief:
        instructions = {
            "harder": "Сделай подачу жёстче и конкретнее, но не добавляй новых фактов.",
            "meme": "Сделай подачу мемнее: узнаваемая ситуация и один сильный панч без клоунады.",
            "short": "Сократи монолог примерно на 15%, сохрани хук, смысл и законченный финал.",
            "hook": "Сохрани основную мысль, но придумай совершенно другой сильный хук.",
        }
        if mode not in instructions:
            raise ValueError(f"Неизвестный режим сценария: {mode}")
        source = json.dumps(brief.to_dict(), ensure_ascii=False)
        raw = await self.editor.llm(
            CHANNELS[brief.channel]["voice"],
            f"{SCRIPT_CONTRACT}\n{instructions[mode]}\nВерни весь обновлённый JSON.\n\nТЕКУЩАЯ ВЕРСИЯ:\n{source}",
            .94,
        )
        data = self._parse(raw)
        data.update(channel=brief.channel, draft_id=brief.draft_id)
        updated = ShortBrief.from_legacy(data)
        updated.delivery_preset = brief.delivery_preset
        updated.voice_preset = brief.voice_preset
        updated.subtitle_preset = brief.subtitle_preset
        self.validate(updated)
        return updated

    @staticmethod
    def _parse(raw: str) -> dict:
        text = (raw or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Shorts: модель не вернула JSON")
        return json.loads(text[start:end + 1])

    @staticmethod
    def validate(brief: ShortBrief) -> None:
        if not brief.title or not brief.hook or not brief.voiceover or not brief.cta:
            raise ValueError("Shorts: сценарий неполный")
        if not 5 <= len(brief.scenes) <= 10:
            raise ValueError("Shorts: нужно 5–10 сцен")
        if not 38 <= brief.word_count <= 70:
            raise ValueError(f"Shorts: озвучка {brief.word_count} слов, допустимо 38–70")
        if not 20 <= brief.duration <= 35:
            raise ValueError(f"Shorts: длительность сцен {brief.duration} сек, допустимо 20–35")
        if len(plain_text(brief.hook).split()) > 18:
            raise ValueError("Shorts: хук слишком длинный для первых двух секунд")
