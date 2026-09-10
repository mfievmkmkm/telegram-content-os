from zoneinfo import ZoneInfo

from content_os.database import Database
from content_os.topic_rotation import TopicRotation, topical_similarity


def test_similarity_detects_same_subject_but_not_new_lane():
    assert topical_similarity("Почему floor не доказывает ликвидность", "Дешёвый floor не означает ликвидный подарок") >= .5
    assert topical_similarity("восстановление и сон игрока", "фишинговая ссылка на подарок") == 0


def test_rotation_advances_and_returns_broad_choices(tmp_path):
    db=Database(str(tmp_path/"content.db"),ZoneInfo("UTC")); db.init()
    rotation=TopicRotation(db)
    first=rotation.next("gifts")
    second=rotation.next("gifts")
    assert first != second
    assert len({item.lane for item in rotation.choices("gifts",8)}) == 8


def test_full_gifts_cycle_does_not_repeat_a_lane(tmp_path):
    db=Database(str(tmp_path/"content.db"),ZoneInfo("UTC")); db.init()
    choices=TopicRotation(db).choices("gifts",30)
    assert len(choices) == 30
    assert len({item.lane for item in choices}) == 30
