from content_os.channels import CHANNELS, CONTENT_LANES, FORMAT_ROTATION, FORMAT_RULES
from content_os.editor import Editor


def test_both_channels_have_short_and_meme_formats():
    for channel in ("gifts","liga"):
        assert "мем" in CHANNELS[channel]["formats"]
        assert "короткий_удар" in CHANNELS[channel]["formats"]
        assert len(CHANNELS[channel]["formats"]) == len(CHANNELS[channel]["format_weights"])


def test_meme_is_not_forced_into_longread_length():
    rule=Editor.format_rule("мем")
    assert "100–260" in rule
    assert "статья" in rule
    assert "мем" in FORMAT_RULES


def test_editorial_rotation_guarantees_variety():
    for channel in ("gifts","liga"):
        rotation=FORMAT_ROTATION[channel]
        assert rotation.count("мем")>=2
        assert "короткий_удар" in rotation
        assert len(CONTENT_LANES[channel])>=7


def test_gifts_is_a_broad_editorial_product_not_a_floor_feed():
    lanes=" ".join(CONTENT_LANES["gifts"]).lower()
    assert len(CONTENT_LANES["gifts"]) >= 28
    for subject in ("идентич", "создател", "сообщест", "дизайн", "безопас", "mini apps", "приватност"):
        assert subject in lanes
    assert CHANNELS["gifts"]["formats"].count("рынок_за_минуту") == 1
    assert FORMAT_ROTATION["gifts"].count("рынок_за_минуту") == 1
    assert "кейс" in FORMAT_RULES
