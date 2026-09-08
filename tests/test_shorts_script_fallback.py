import asyncio

from content_os.shorts.script import ShortScriptService


class BrokenEditor:
    async def llm(self, *_args):
        return "Я не смог вернуть JSON, но вот сценарий обычным текстом"


class IncompleteEditor:
    async def llm(self, *_args):
        return '{"title":"x","hook":"x","voiceover":"слишком коротко","scenes":[],"caption":"x","music_mood":"x","cta":"x"}'


def test_invalid_llm_json_produces_reviewable_script():
    service = ShortScriptService(BrokenEditor())
    draft = {"id": 12, "channel_key": "gifts", "text": "Ты смотришь только на floor. Редкая модель может изменить решение, поэтому сначала проверь контекст и ликвидность."}
    brief = asyncio.run(service.prepare(draft))
    assert 64 <= brief.word_count <= 105
    assert len(brief.scenes) == 8
    assert 28 <= brief.duration <= 50
    assert brief.draft_id == 12


def test_structurally_valid_but_incomplete_script_is_rebuilt():
    service=ShortScriptService(IncompleteEditor())
    draft={"id":13,"channel_key":"liga","text":"Игрок видит мяч слишком поздно. Сканирование до приёма открывает следующий ход. Сделай три взгляда через плечо до передачи и оцени решение после упражнения."}
    brief=asyncio.run(service.prepare(draft))
    assert brief.word_count>=64
    assert brief.duration==32
