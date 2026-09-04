from content_os.football import fixtures_keyboard_rows


def test_fixture_buttons_keep_api_id():
    fixtures=[{"fixture":{"id":123,"date":"2026-09-03T20:30:00+05:00"},
               "teams":{"home":{"name":"Manchester United"},"away":{"name":"Liverpool"}}}]
    rows=fixtures_keyboard_rows(fixtures)
    assert rows[0][1] == 123
    assert rows[0][0].startswith("20:30")
    assert not rows[0][0].endswith("· ")
