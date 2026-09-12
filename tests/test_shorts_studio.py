import asyncio

from content_os.shorts.models import ShortBrief, ShortScene, ShortStage
from content_os.shorts.presets import delivery, voice
from content_os.shorts.script import ShortScriptService


def sample_brief():
    return ShortBrief(
        title="Не смотри только на floor",
        hook="Floor показывает далеко не всё",
        voiceover=" ".join(["слово"] * 80),
        scenes=[ShortScene(4, f"scene {index}") for index in range(8)],
        caption="caption",
        music_mood="tension",
        cta="Проверяешь модель?",
        channel="gifts",
        draft_id=42,
    )


def test_script_is_review_first():
    brief = sample_brief()
    assert brief.stage == ShortStage.SCRIPT
    assert brief.approved is False
    brief.approve_script()
    assert brief.stage == ShortStage.VOICE
    assert brief.approved is True


def test_targeted_edit_invalidates_only_requested_stage():
    brief = sample_brief()
    brief.approve_script()
    brief.invalidate_from(ShortStage.SCENES)
    assert brief.stage == ShortStage.SCENES
    assert brief.approved is True
    brief.invalidate_from(ShortStage.SCRIPT)
    assert brief.approved is False


def test_presets_have_production_defaults():
    assert delivery("meme").key == "meme"
    assert voice("auto_ru").provider == "elevenlabs"
    assert voice("missing").key == "auto_ru"


def test_script_validation_accepts_complete_brief():
    brief = sample_brief()
    ShortScriptService.validate(brief)
    assert brief.duration == 32
    assert brief.word_count == 80


class BrokenEditor:
    async def llm(self, system, prompt, temperature): return "not json"


def test_dirty_hook_button_has_a_distinct_safe_fallback():
    original=sample_brief()
    changed=asyncio.run(ShortScriptService(BrokenEditor()).rewrite(original,"dirty"))
    assert changed.hook != original.hook
    assert len(changed.hook.split()) <= 12
    assert 64 <= changed.word_count <= 105
    assert changed.voiceover.endswith(tuple(".!?"))
