import pytest
import asyncio
from types import SimpleNamespace

from content_os.video import VideoFactory


def valid_payload():
    return {"title":"t","hook":"h","voiceover":"v","caption":"c","music_mood":"m","cta":"x",
            "scenes":[{"seconds":6,"visual":"pitch","screen_text":"Стоп"} for _ in range(5)]}


def test_video_payload_is_valid():
    VideoFactory.validate(valid_payload())


def test_short_video_is_rejected():
    data=valid_payload()
    for scene in data["scenes"]: scene["seconds"]=2
    with pytest.raises(ValueError): VideoFactory.validate(data)
def test_json_can_be_extracted_from_model_chatter():
    data=VideoFactory.parse_json('Вот результат:\n```json\n{"title":"x"}\n```')
    assert data["title"]=="x"


def test_mpt_nested_response_is_unwrapped():
    assert VideoFactory._data({"status":200,"data":{"task_id":"abc"}})["task_id"]=="abc"


def test_busy_worker_gateway_error_is_transient():
    assert VideoFactory.transient_status_error(RuntimeError('MoneyPrinterTurbo HTTP 502: Application failed to respond'))
    assert not VideoFactory.transient_status_error(RuntimeError('MoneyPrinterTurbo HTTP 401: invalid key'))
    assert not VideoFactory.transient_status_error(RuntimeError('MoneyPrinterTurbo HTTP 404: task not found'))


def test_mpt_payload_always_contains_broad_stock_queries():
    factory=VideoFactory(SimpleNamespace(mpt_voice_name="ru-RU-DmitryNeural"),None,None)
    data=valid_payload(); data["channel"]="liga"
    payload=factory.mpt_payload(data)
    assert payload["video_terms"][0]=="football training"
    assert "soccer field" in payload["video_terms"]
    assert payload["video_concat_mode"]=="random"


def test_missing_json_fields_fall_back_to_complete_brief():
    class EmptyEditor:
        async def llm(self,*args,**kwargs): return "{}"
    class MemoryDb:
        def save_video_job(self,draft_id,payload):
            self.payload=payload; return 7
    db=MemoryDb(); factory=VideoFactory(SimpleNamespace(mpt_webhook_url=""),db,EmptyEditor())
    job,data,_,_=asyncio.run(factory.create({"id":3,"channel_key":"liga","text":"<b>Ты проиграл эпизод ещё до приёма мяча.</b>\n\nСканируй поле до передачи.\n\nА ты смотришь через плечо?"}))
    assert job==7
    VideoFactory.validate(data)
    assert len(data["scenes"])==7
    assert data["hook"].startswith("Ты проиграл")
