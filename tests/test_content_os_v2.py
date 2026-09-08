from content_os.content_fingerprint import ContentFingerprint, lexical_similarity, repetition_gate
from content_os.creative_director import inspect_content
from content_os.visual_director import choose_concepts


def fp(**changes):
    data = dict(topic="valuation", angle="model_over_floor", hook_type="loss", format_key="guide", emotion="fomo", cta_type="tracker")
    data.update(changes)
    return ContentFingerprint(**data)


def test_repetition_gate_blocks_same_editorial_mechanic():
    decision = repetition_gate(fp(), "Новый текст", [(fp(), "Совсем другой текст")])
    assert not decision.allowed
    assert decision.score >= .70


def test_lexical_similarity_detects_near_copy():
    assert lexical_similarity("Смотри не только на floor, смотри на model", "Смотри не только на floor — смотри на model") > .85


def test_director_blocks_high_similarity():
    report = inspect_content("Хук\n" + "Нормальный конкретный текст " * 20, channel="gifts", similarity_score=.84)
    assert not report.approved
    assert any(issue.code == "duplicate" for issue in report.issues)


def test_director_flags_numeric_gifts_claims_for_fact_pack():
    report = inspect_content("Хук\n" + "Рынок вырос на 30% и это надо проверить. " * 10, channel="gifts")
    assert any(issue.code == "facts_required" for issue in report.issues)


def test_visual_director_avoids_recent_compositions_first():
    concepts = choose_concepts("gifts", ["terminal", "collectible"], count=3)
    assert concepts[0].key not in {"terminal", "collectible"}
