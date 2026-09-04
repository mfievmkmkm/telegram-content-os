import pytest

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


def test_jersey_colour_uses_torso_pixels():
    np=pytest.importorskip("numpy"); pytest.importorskip("cv2")
    from matchlens_service.visuals import jersey_color
    blue=np.zeros((120,60,3),dtype=np.uint8); blue[:]=(220,40,20)
    white=np.full((120,60,3),235,dtype=np.uint8)
    assert jersey_color(blue)=="blue"
    assert jersey_color(white)=="white"


def test_player_wall_is_created(tmp_path):
    np=pytest.importorskip("numpy"); pytest.importorskip("cv2")
    from matchlens_service.visuals import player_wall
    output=tmp_path/"players.jpg"; crop=np.full((160,80,3),(220,40,20),np.uint8)
    player_wall({7:crop},{"7":{"visibility_percent":44.5,"jersey_color":"blue"}},output)
    assert output.exists() and output.stat().st_size>1000
