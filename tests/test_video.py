import pytest

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
