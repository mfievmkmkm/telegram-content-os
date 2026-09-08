import asyncio

from content_os.shorts.script import ShortScriptService


class BrokenEditor:
    async def llm(self, *_args):
        return "Я не смог вернуть JSON, но вот сценарий обычным текстом"


class IncompleteEditor:
    async def llm(self, *_args):
        return '{"title":"x","hook":"x","voiceover":"слишком коротко","scenes":[],"caption":"x","music_mood":"x","cta":"x"}'


class LongHookEditor:
    async def llm(self, *_args):
        words = " ".join(f"хук{i}" for i in range(25))
        voice = " ".join(f"слово{i}" for i in range(75))
        scenes = ",".join(f'{{"seconds":4,"visual":"scene {i}","screen_text":"copy {i}"}}' for i in range(8))
        return f'{{"title":"длинный заголовок","hook":"{words}","voiceover":"{voice}","scenes":[{scenes}],"caption":"caption","music_mood":"dark","cta":"cta"}}'


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


def test_long_hook_is_compacted_instead_of_rejecting_harder_result():
    service=ShortScriptService(LongHookEditor())
    draft={"id":14,"channel_key":"gifts","text":"Исходный пост с достаточным контекстом для сценария."}
    brief=asyncio.run(service.prepare(draft))
    assert len(brief.hook.split()) == 16
    assert brief.hook.endswith("!")
    assert brief.word_count == 75
