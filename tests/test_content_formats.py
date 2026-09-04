from content_os.channels import CHANNELS, FORMAT_RULES
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
