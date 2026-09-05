from content_os.shorts.models import ShortBrief, ShortScene, ShortStage
from content_os.shorts.session import ShortSessionStore
from content_os.shorts.ui import brief_text, review_keyboard, voice_keyboard
from shorts_service.subtitles import subtitle_style


class MemoryDB:
    def __init__(self): self.data = {}
    def get(self, key): return self.data.get(key)
    def set(self, key, value): self.data[key] = value


def sample_brief():
    return ShortBrief(
        title="Ошибка оценки",
        hook="Ты смотришь не туда",
        voiceover=" ".join(["слово"] * 48),
        scenes=[ShortScene(4, f"scene {i}") for i in range(6)],
        caption="caption",
        music_mood="tension",
        cta="Проверь ещё раз",
        channel="gifts",
        draft_id=42,
    )


def test_session_store_keeps_review_state():
    store = ShortSessionStore(MemoryDB())
    brief = sample_brief()
    store.save(7, brief)
    loaded = store.load(7)
    assert loaded is not None
    assert loaded.draft_id == 42
    assert loaded.stage == ShortStage.SCRIPT
    approved = store.approve(7)
    assert approved.approved is True
    assert approved.stage == ShortStage.VOICE
    changed = store.choose_voice(7, "ru_lera")
    assert changed.voice_preset == "ru_lera"
    assert changed.stage == ShortStage.VOICE
    styled = store.choose_style(7, "meme")
    assert styled.delivery_preset == "meme"
    assert styled.approved is False
    assert styled.stage == ShortStage.SCRIPT


def test_ui_is_review_first_and_readable():
    brief = sample_brief()
    text = brief_text(brief)
    assert "SHORTS STUDIO" in text
    assert "Монтаж начнётся только после подтверждения" in text
    labels = [button.text for row in review_keyboard(7).inline_keyboard for button in row]
    assert "✅ В монтаж" in labels
    assert "✂️ Короче" in labels
    voice_labels = [button.text for row in voice_keyboard(7, "gifts").inline_keyboard for button in row]
    assert any("Lera" in label for label in voice_labels)


def test_subtitle_presets_are_distinct():
    punch = subtitle_style("punch")
    clean = subtitle_style("clean")
    assert punch.font_size != clean.font_size
    assert punch.max_words != clean.max_words
    assert subtitle_style("unknown").key == "punch"
