import asyncio
from types import SimpleNamespace

import pytest

from content_os.matchlens import MatchLensClient, MatchRequest, aggregate_passport, confidence_legend


class FakeDb:
    def __init__(self): self.rows={}; self.next_id=1
    def save_match_job(self,source_type,source_ref,player_ref,analysis_mode):
        job_id=self.next_id; self.next_id+=1
        self.rows[job_id]={"id":job_id,"external_id":None,"source_type":source_type,"source_ref":source_ref,
                           "player_ref":player_ref,"analysis_mode":analysis_mode,"status":"queued","progress":0,
                           "result_url":None,"error":None}
        return job_id
    def update_match_job(self,job_id,**fields): self.rows[job_id].update(fields)
    def match_job(self,job_id): return self.rows.get(job_id)


def settings(base_url=""):
    return SimpleNamespace(matchlens_base_url=base_url,matchlens_api_key="secret",matchlens_timeout_minutes=180)


def test_match_request_rejects_non_http_url():
    with pytest.raises(ValueError): MatchRequest("url","not-a-url","№7").validate()


def test_match_request_accepts_player_description():
    MatchRequest("url","https://example.com/match.mp4","№7, синяя форма","player").validate()


def test_submit_saves_queued_job_without_worker():
    db=FakeDb(); client=MatchLensClient(settings(),db)
    local_id,external=asyncio.run(client.submit(MatchRequest("url","https://example.com/match.mp4","№7")))
    assert local_id == 1
    assert external is None
    assert db.rows[1]["status"] == "queued"


def test_confidence_legend_never_hides_missing_data():
    legend=confidence_legend()
    assert "Измерено" in legend and "Оценено" in legend and "Не видно" in legend


def test_passport_aggregates_only_observable_video_metrics():
    matches=[{"metrics_json":'{"duration_seconds":600,"selected_player":{"visibility_percent":40,"movement_index":12,"zones_percent":{"left":70,"centre":20,"right":10},"burst_timestamps":[5,20]}}'}]
    result=aggregate_passport(matches)
    assert result=={"count":1,"video_minutes":10,"visibility":40,"movement":12,"zone":"left","moments":2}
    assert "distance" not in result and "speed" not in result
