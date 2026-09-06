import asyncio

from content_os.shorts.script import ShortScriptService


class BrokenEditor:
    async def llm(self, *_args):
        return "Я не смог вернуть JSON, но вот сценарий обычным текстом"


def test_invalid_llm_json_produces_reviewable_script():
    service = ShortScriptService(BrokenEditor())
    draft = {"id": 12, "channel_key": "gifts", "text": "Ты смотришь только на floor. Редкая модель может изменить решение, поэтому сначала проверь контекст и ликвидность."}
    brief = asyncio.run(service.prepare(draft))
    assert 42 <= brief.word_count <= 70
    assert len(brief.scenes) == 6
    assert 20 <= brief.duration <= 35
    assert brief.draft_id == 12
