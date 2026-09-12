import asyncio
import json

import pytest

from content_os.remix import RemixService


class FakeEditor:
    async def llm(self, system, prompt, temperature):
        return json.dumps({
            "telegram_long":"Большой оригинальный разбор с одной полезной мыслью и конкретным применением для читателя.",
            "telegram_short":"Короткий другой угол той же идеи, а не обрезанная версия большого поста.",
            "meme":"Когда увидел важную деталь уже после того, как все всё поняли.",
            "poll_question":"Что ты проверяешь первым?",
            "poll_options":["Контекст","Детали","Результат"],
            "shorts_script":"Ты замечаешь очевидное слишком поздно. Сначала проверь контекст, потом ключевую деталь, и только после этого делай вывод. Именно порядок проверки чаще всего спасает от глупой ошибки. Если нужен полный разбор — он уже в канале.",
            "sales_bridge":"Если хочешь разобрать свою ситуацию, начни с диагностики — без покупки вслепую.",
        }, ensure_ascii=False)


class AliasEditor:
    async def llm(self, system, prompt, temperature):
        return json.dumps({
            "long_post":"Полный разбор идеи с конфликтом, объяснением и понятным действием для читателя.",
            "short_post":"Короткая версия с другим углом и самостоятельной мыслью.",
            "meme_text":"Я всё проверил. Проверку решил не проверять.",
            "poll":{"question":"Что ломает решение?","options":["Спешка","Самоуверенность"]},
            "video_script":"Это сценарий ролика, который модель почему-то назвала иначе, но его нельзя выбрасывать из-за имени поля.",
            "cta":"Сохрани разбор и проверь свой выбор ещё раз.",
        },ensure_ascii=False)


class BrokenEditor:
    async def llm(self, system, prompt, temperature): return "совсем не json"


def test_remix_parses_distinct_bundle():
    bundle=asyncio.run(RemixService(FakeEditor()).create("gifts","Это достаточно длинная исходная идея про ошибку оценки объекта и порядок проверки деталей перед решением."))
    assert len(bundle.poll_options)==3
    assert bundle.telegram_long != bundle.telegram_short
    assert "диагност" in bundle.sales_bridge.lower()


def test_remix_rejects_bad_poll():
    bad=json.dumps({
        "telegram_long":"нормальный длинный текст",
        "telegram_short":"нормальный короткий текст",
        "meme":"нормальная мемная формулировка",
        "poll_question":"нормальный вопрос",
        "poll_options":["один"],
        "shorts_script":"нормальный сценарий ролика",
        "sales_bridge":"нормальный переход к действию",
    })
    with pytest.raises(ValueError,match="2–4"):
        RemixService.parse(bad)


def test_remix_accepts_common_model_aliases():
    bundle=asyncio.run(RemixService(AliasEditor()).create("gifts","Исходная идея достаточно длинная, чтобы собрать из неё несколько самостоятельных форматов без выдуманных фактов."))
    assert "сценарий" in bundle.shorts_script.lower()
    assert bundle.poll_options == ("Спешка","Самоуверенность")


def test_remix_never_dead_ends_after_two_broken_answers():
    bundle=asyncio.run(RemixService(BrokenEditor()).create("liga","Игрок дважды не посмотрел через плечо перед приёмом мяча и потерял возможность продолжить атаку."))
    assert len(bundle.poll_options) >= 2
    assert 64 <= len(bundle.shorts_script.split()) <= 105
    assert bundle.sales_bridge
