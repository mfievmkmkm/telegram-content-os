from matchlens_service.analytics import coach_notes, player_report


def test_player_report_has_zones_bursts_and_confidence():
    points = [(index / 4, .1 + index / 1000, .5) for index in range(120)]
    report = player_report(points, 60)
    assert report["visibility_percent"] == 50
    assert report["zones_percent"]["left"] == 100
    assert len(report["burst_timestamps"]) == 5
    assert report["confidence"] == "high"


def test_coach_notes_never_claim_gps_distance():
    report = player_report([(0, .5, .5), (.25, .6, .5)], 10)
    notes = coach_notes(report)
    assert any("GPS" in note for note in notes)
    assert any("центральном" in note for note in notes)
