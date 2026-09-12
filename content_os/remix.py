from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .channels import CHANNELS, POST_RULES
from .formatting import clean_generated_post, plain_text


@dataclass(frozen=True)
class RemixBundle:
    telegram_long: str
    telegram_short: str
    meme: str
    poll_question: str
    poll_options: tuple[str, ...]
    shorts_script: str
    sales_bridge: str


class RemixService:
    """Turn one proven idea into channel-native formats, not seven summaries."""

    def __init__(self, editor):
        self.editor = editor

    async def create(self, channel_key: str, source_text: str) -> RemixBundle:
        if channel_key not in CHANNELS:
            raise ValueError(f"Unknown channel: {channel_key}")
        clean = (source_text or "").strip()
        if len(clean) < 40:
            raise ValueError("Remix needs a real source idea, not a title")
        prompt = self._prompt(channel_key, clean)
        raw = await self.editor.llm(CHANNELS[channel_key]["voice"] + POST_RULES, prompt, .84)
        try:
            return self.parse(raw)
        except (ValueError, TypeError, json.JSONDecodeError) as first_error:
            repair_prompt = (
                "Исправь ответ CONTENT REMIX. Не переписывай удачные части. Верни один JSON-объект "
                "строго с полями telegram_long, telegram_short, meme, poll_question, poll_options, "
                "shorts_script, sales_bridge. poll_options — массив из 2–4 строк. Никакого markdown.\n\n"
                f"ОШИБКА: {first_error}\n\nИСХОДНАЯ ИДЕЯ:\n{clean[:5000]}\n\nОТВЕТ ДЛЯ РЕМОНТА:\n{raw[:7000]}"
            )
            try:
                repaired = await self.editor.llm(CHANNELS[channel_key]["voice"] + POST_RULES, repair_prompt, .55)
                return self.parse(repaired)
            except (ValueError, TypeError, json.JSONDecodeError):
                # A flaky model must not turn a paid operator action into a dead
                # button. The fallback preserves the source and every output slot.
                return self.fallback(channel_key, clean)

    @staticmethod
    def _prompt(channel_key: str, source_text: str) -> str:
        vertical = "Telegram Gifts" if channel_key == "gifts" else "футболисты и развитие игрока"
        return (
            "CONTENT REMIX. Одна идея должна дать разные причины потреблять каждый формат. "
            "Не сокращай один и тот же текст семь раз. Не придумывай цифры, цитаты, матчи, цены или рыночные факты. "
            f"Аудитория: {vertical}. Верни ТОЛЬКО валидный JSON без markdown.\n\n"
            "Поля JSON:\n"
            "telegram_long — 700–1400 знаков, полезный разбор;\n"
            "telegram_short — 250–500 знаков, другой угол;\n"
            "meme — setup + punchline, максимум 180 знаков;\n"
            "poll_question — спорный, но честный вопрос;\n"
            "poll_options — массив 2–4 коротких вариантов;\n"
            "shorts_script — 64–105 слов, законченная дуга hook/body/payoff/CTA без служебных заголовков;\n"
            "sales_bridge — нативный переход к следующему действию без ложного дефицита.\n\n"
            f"ИСХОДНАЯ ИДЕЯ:\n{source_text[:7000]}"
        )

    @staticmethod
    def parse(raw: str) -> RemixBundle:
        value = (raw or "").strip()
        if value.startswith("```"):
            value = value.strip("`")
            if value.lower().startswith("json"):
                value = value[4:].lstrip()
        start, end = value.find("{"), value.rfind("}")
        if start >= 0 and end >= start:
            value = value[start:end + 1]
        try:
            data = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("Remix LLM returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("Remix response must be a JSON object")
        for wrapper in ("remix", "data", "formats", "result"):
            if isinstance(data.get(wrapper), dict):
                data = data[wrapper]
                break
        poll = data.get("poll") if isinstance(data.get("poll"), dict) else {}
        aliases = {
            "telegram_long": ("long", "long_post", "telegram_post"),
            "telegram_short": ("short", "short_post"),
            "meme": ("meme_post", "meme_text"),
            "poll_question": ("question",),
            "poll_options": ("options",),
            "shorts_script": ("shorts", "video_script", "voiceover", "reels_script"),
            "sales_bridge": ("sales", "cta", "sales_cta", "bridge"),
        }
        data = dict(data)
        for canonical, candidates in aliases.items():
            if data.get(canonical) not in (None, "", []):
                continue
            data[canonical] = next((data[key] for key in candidates if data.get(key) not in (None, "", [])), None)
        data["poll_question"] = data.get("poll_question") or poll.get("question")
        data["poll_options"] = data.get("poll_options") or poll.get("options")
        required = ("telegram_long", "telegram_short", "meme", "poll_question", "poll_options", "shorts_script", "sales_bridge")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"Remix response misses fields: {', '.join(missing)}")
        options = tuple(str(item).strip() for item in data["poll_options"] if str(item).strip()) if isinstance(data["poll_options"], list) else ()
        if not 2 <= len(options) <= 4:
            raise ValueError("Remix poll_options must contain 2–4 options")
        texts = {key: clean_generated_post(str(data[key])).strip() for key in required if key != "poll_options"}
        if any(len(text) < 8 for text in texts.values()):
            raise ValueError("Remix response contains an empty format")
        return RemixBundle(
            telegram_long=texts["telegram_long"],
            telegram_short=texts["telegram_short"],
            meme=texts["meme"],
            poll_question=texts["poll_question"],
            poll_options=options,
            shorts_script=texts["shorts_script"],
            sales_bridge=texts["sales_bridge"],
        )

    @staticmethod
    def fallback(channel_key: str, source_text: str) -> RemixBundle:
        source = plain_text(clean_generated_post(source_text)).strip()
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", source) if item.strip()]
        first = (sentences[0] if sentences else source)[:170].rstrip(" .")
        short = " ".join(sentences[:3]).strip()[:500].rstrip(" ,;:")
        if short and short[-1] not in ".!?": short += "?"
        voice = " ".join(sentences).strip()
        bridge = (
            "Хочешь отличать красивую упаковку от сильной идеи — сохрани разбор и проверь свой выбор"
            if channel_key == "gifts" else
            "Хочешь увидеть такую ошибку в своей игре — начни с разбора одного эпизода"
        )
        filler = (
            " Сначала убери спешку. Посмотри на контекст, проверь главную деталь и только потом делай вывод."
            " Сильное решение обычно выглядит проще, потому что в нём нет попытки угадать всё сразу."
        )
        while len(voice.split()) < 64:
            voice += filler
        voice = " ".join(voice.split()[:100]).rstrip(" ,;:")
        if voice and voice[-1] not in ".!?": voice += "."
        question = "Что здесь чаще всего ломает решение?"
        return RemixBundle(
            telegram_long=source,
            telegram_short=short or first,
            meme=f"Когда понял «{first[:95]}» уже после своего гениального решения",
            poll_question=question,
            poll_options=("Спешка", "Самоуверенность", "Нет проверки"),
            shorts_script=voice,
            sales_bridge=bridge,
        )
