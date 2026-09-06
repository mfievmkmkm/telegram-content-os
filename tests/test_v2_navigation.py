from content_os.football_challenge_runtime import _keyboard
from content_os.football_challenges import LIBRARY
from content_os.operator_runtime import HOME_CALLBACK, home_nav, operator_keyboard, section_nav
from content_os.ui import projects_keyboard, studio_keyboard


def callbacks(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


def test_v2_surfaces_never_go_back_to_legacy_home(monkeypatch):
    monkeypatch.delenv("MINIAPP_PUBLIC_URL", raising=False)
    surfaces = [home_nav(), operator_keyboard(), studio_keyboard(), projects_keyboard(), _keyboard(LIBRARY[0])]
    for surface in surfaces:
        assert "panel:home" not in callbacks(surface)
    assert HOME_CALLBACK in callbacks(home_nav())
    assert all(button.callback_data != "panel:home" for row in section_nav() for button in row)


def test_home_has_miniapp_launch_when_public_url_exists(monkeypatch):
    monkeypatch.setenv("MINIAPP_PUBLIC_URL", "https://content.example")
    first = operator_keyboard().inline_keyboard[0][0]
    assert first.web_app.url == "https://content.example"
