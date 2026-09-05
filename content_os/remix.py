from __future__ import annotations

import json
from dataclasses import dataclass

from .channels import CHANNELS, POST_RULES
from .formatting import clean_generated_post


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
        return self.parse(raw)

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
            "shorts_script — 42–70 слов, hook/body/payoff/CTA без служебных заголовков;\n"
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
        try:
            data = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("Remix LLM returned invalid JSON") from exc
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
