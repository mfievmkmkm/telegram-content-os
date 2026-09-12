from __future__ import annotations

import json
import re

from ..channels import CHANNELS
from ..formatting import plain_text
from .models import ShortBrief
from .presets import delivery


SCRIPT_CONTRACT = """Создай сценарий вертикального ролика 9:16 длительностью 30–45 секунд.
Сначала качество текста, монтаж будет только после подтверждения редактором.
Хук обязан остановить скролл за первые 2 секунды: конкретная боль, конфликт, неожиданность или опасное заблуждение.
Никаких приветствий и AI-канцелярита. Каждое предложение короткое и произносимое вслух.
Это самостоятельная видеоверсия, а не обрезанный первый абзац. Сохрани хук, все ключевые тезисы,
практическое действие и финальный вывод исходника. Можно сжать повторы, но нельзя бросать мысль на середине
или выбрасывать вторую половину смысла. Монолог обязан иметь дугу: конфликт → объяснение → решение → финал.
Не придумывай цены, статистику, цитаты или события.
Верни СТРОГО JSON без markdown:
{"title":"...","hook":"...","voiceover":"...","scenes":[{"seconds":4,"visual":"English visual intent","screen_text":"...","asset_type":"stock_video"}],"caption":"...","music_mood":"...","cta":"..."}
Сделай 8–10 сцен общей длительностью 30–45 секунд.
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
        try:
            data = self._parse(raw)
        except (ValueError, TypeError, json.JSONDecodeError):
            data = self._fallback(draft)
        try:
            data.update(channel=draft["channel_key"], draft_id=draft["id"])
            brief = ShortBrief.from_legacy(data)
            brief.delivery_preset = delivery_key
            self._normalize(brief)
            self.validate(brief)
        except (ValueError, TypeError, AttributeError):
            data=self._fallback(draft); data.update(channel=draft["channel_key"],draft_id=draft["id"])
            brief=ShortBrief.from_legacy(data); brief.delivery_preset=delivery_key; self.validate(brief)
        return brief

    async def rewrite(self, brief: ShortBrief, mode: str) -> ShortBrief:
        instructions = {
            "harder": "Сделай подачу жёстче и конкретнее, но не добавляй новых фактов.",
            "meme": "Сделай подачу мемнее: узнаваемая ситуация и один сильный панч без клоунады.",
            "short": "Сократи монолог примерно на 15%, сохрани хук, смысл и законченный финал.",
            "hook": "Сохрани основную мысль, но придумай совершенно другой сильный хук.",
            "dirty": (
                "Максимально зацепи зрителя в первые 3 секунды. Подача грязная и провокационная: "
                "ударь по самоуверенности, страху потери или неприятной правде. Хук 5–12 слов. "
                "Никаких выдуманных фактов, оскорблений аудитории, ложной срочности и обещаний прибыли. "
                "Грязно по энергии, чисто по фактам."
            ),
        }
        if mode not in instructions:
            raise ValueError(f"Неизвестный режим сценария: {mode}")
        source = json.dumps(brief.to_dict(), ensure_ascii=False)
        raw = await self.editor.llm(
            CHANNELS[brief.channel]["voice"],
            f"{SCRIPT_CONTRACT}\n{instructions[mode]}\nВерни весь обновлённый JSON.\n\nТЕКУЩАЯ ВЕРСИЯ:\n{source}",
            .94,
        )
        try:
            data = self._parse(raw)
        except (ValueError, TypeError, json.JSONDecodeError):
            return self._fallback_rewrite(brief, mode)
        try:
            data.update(channel=brief.channel, draft_id=brief.draft_id)
            updated = ShortBrief.from_legacy(data)
            updated.delivery_preset = brief.delivery_preset
            updated.voice_preset = brief.voice_preset
            updated.subtitle_preset = brief.subtitle_preset
            self._normalize(updated)
            self.validate(updated)
        except (ValueError, TypeError, AttributeError):
            return self._fallback_rewrite(brief, mode)
        return updated

    def _fallback_rewrite(self, brief: ShortBrief, mode: str) -> ShortBrief:
        """Make every control visibly useful even when the LLM breaks JSON."""
        data = brief.to_dict()
        hooks = {
            "harder": "Ты проигрываешь ещё до проверки главной детали",
            "meme": "Ты всё проверил. Кроме того, что реально решает",
            "short": brief.hook,
            "hook": "Вот где уверенность превращается в ловушку",
            "dirty": "Тебя сейчас подставит твоя же уверенность",
        }
        if brief.channel == "liga":
            hooks.update({
                "harder": "Соперник уже наказал ошибку, которую ты не заметил",
                "meme": "Ты сыграл идеально. Мяч почему-то у соперника",
                "hook": "Эту мелочь тренер замечает раньше твоего гола",
                "dirty": "Тренер уже видит, почему тебя посадят",
            })
        hook = hooks[mode]
        words = brief.voiceover.split()
        if mode == "short" and len(words) > 68:
            words = words[:54] + words[-12:]
        voice = " ".join(words).strip()
        old_hook = plain_text(brief.hook).strip()
        if mode != "short" and hook.lower() not in voice.lower():
            if old_hook and voice.lower().startswith(old_hook.lower()):
                voice = voice[len(old_hook):].lstrip(" .!?:—–-")
            voice = f"{hook}. {voice}".strip()
        while len(voice.split()) < 64:
            voice += " Проверь контекст, найди главную деталь и только потом принимай решение."
        if len(voice.split()) > 105:
            voice_words = voice.split()
            voice = " ".join(voice_words[:90] + voice_words[-15:]).rstrip(" ,;:")
        if voice and voice[-1] not in ".!?": voice += "."
        data.update(hook=hook, title=hook[:70], voiceover=voice)
        updated = ShortBrief.from_legacy(data)
        updated.delivery_preset = brief.delivery_preset
        updated.voice_preset = brief.voice_preset
        updated.subtitle_preset = brief.subtitle_preset
        self._normalize(updated)
        self.validate(updated)
        return updated

    @staticmethod
    def _normalize(brief: ShortBrief) -> None:
        """Repair harmless LLM contract drift without discarding good copy."""
        hook = plain_text(brief.hook).strip()
        words = hook.split()
        if len(words) > 18:
            # Aim below the hard limit so punctuation and later formatting cannot
            # turn a two-second hook into a breathless sentence.
            hook = " ".join(words[:16]).rstrip(" ,;:—–-")
            if hook and hook[-1] not in ".!?":
                hook += "!"
            brief.hook = hook
            if len(brief.title.split()) > 16:
                brief.title = hook.rstrip("!?")[:70]

    @staticmethod
    def _parse(raw: str) -> dict:
        text = (raw or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Shorts: модель не вернула JSON")
        return json.loads(text[start:end + 1])

    @staticmethod
    def _fallback(draft) -> dict:
        text = plain_text(str(draft.get("text") or "")).strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        hook = (lines[0] if lines else "Здесь есть деталь, которую почти все пропускают")[:110]
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", text) if item.strip()]
        selected=[]
        # Keep the beginning, body and conclusion. This fallback is deliberately
        # sentence-safe: it never slices a word or silently loses the ending.
        for index in sorted(set([0, *range(1, max(1,len(sentences)-1)), max(0,len(sentences)-1)])):
            sentence=sentences[index]
            if len((" ".join(selected+[sentence])).split())<=96:
                selected.append(sentence)
        voice = " ".join(selected).strip(" ,;:")
        safety = " Главное — проверить контекст, увидеть ключевую деталь и только после этого делать вывод."
        while len(voice.split()) < 64:
            voice = (voice + safety).strip()
        voice = " ".join(voice.split()[:100]).rstrip(" ,;:")
        if voice and voice[-1] not in ".!?": voice += "."
        gifts = str(draft.get("channel_key")) == "gifts"
        visuals = (["digital collectible vault 3d", "telegram gift auction 3d", "market whale 3d", "fomo cart 3d", "digital collectible closeup 3d", "telegram market interface"] if gifts else
                   ["football boot impact 3d", "goalkeeper glove catch 3d", "football boot closeup 3d", "goalkeeper save 3d", "football training object 3d", "stadium equipment 3d"])
        captions = [hook, "СМОТРИ ГЛУБЖЕ", "ВОТ ГДЕ ОШИБКА", "НЕ ТЕРЯЙ СМЫСЛ", "РЕШАЕТ ДЕТАЛЬ", "ПРОВЕРЬ КОНТЕКСТ", "ТВОЙ ХОД", "ФИНАЛ"]
        return {"title": hook[:70], "hook": hook, "voiceover": voice,
                "scenes": [{"seconds": 4, "visual": visuals[i % len(visuals)], "screen_text": captions[i][:45], "asset_type": "stock_video"} for i in range(8)],
                "caption": text[:900], "music_mood": "dark electronic tension" if gifts else "energetic sports tension",
                "cta": (lines[-1] if lines else "Сохрани и проверь себя")[:110]}

    @staticmethod
    def validate(brief: ShortBrief) -> None:
        if not brief.title or not brief.hook or not brief.voiceover or not brief.cta:
            raise ValueError("Shorts: сценарий неполный")
        if not 6 <= len(brief.scenes) <= 12:
            raise ValueError("Shorts: нужно 6–12 сцен")
        if not 64 <= brief.word_count <= 105:
            raise ValueError(f"Shorts: озвучка {brief.word_count} слов, допустимо 64–105")
        if not 28 <= brief.duration <= 50:
            raise ValueError(f"Shorts: длительность сцен {brief.duration} сек, допустимо 28–50")
        if len(plain_text(brief.hook).split()) > 18:
            raise ValueError("Shorts: хук слишком длинный для первых двух секунд")
