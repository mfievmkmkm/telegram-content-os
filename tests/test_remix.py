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
