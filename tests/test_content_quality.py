from content_os.content_quality import build_fingerprint, review_candidate


def test_build_fingerprint_detects_conversion_and_warning():
    text = "Эта ошибка съедает твою сделку\n\nПроверь модель перед покупкой. Открой бота"
    fp = build_fingerprint(text=text, topic="gift valuation", angle="model over floor", format_key="guide")
    assert fp.hook_type == "warning"
    assert fp.emotion == "tension"
    assert fp.cta_type == "conversion"


def test_quality_gate_blocks_repeated_editorial_mechanic():
    old_text = "Эта ошибка съедает твою сделку. Смотри модель, а не только floor. Проверь всё перед покупкой"
    old_fp = build_fingerprint(text=old_text, topic="gift valuation", angle="model over floor", format_key="guide")
    new_text = "Эта ошибка может съесть твою сделку. Смотри модель, а не только floor. Проверь всё перед покупкой"
    decision = review_candidate(
        text=new_text,
        channel="gifts",
        topic="gift valuation",
        angle="model over floor",
        format_key="guide",
        history=[(old_fp, old_text)],
    )
    assert decision.approved is False
    assert decision.similarity >= .70
    assert decision.repetition_reason


def test_quality_gate_allows_different_angle():
    old_text = "Почему смотреть только на floor опасно. Проверь модель перед покупкой и не спеши"
    old_fp = build_fingerprint(text=old_text, topic="gift valuation", angle="model over floor", format_key="guide")
    new_text = (
        "Коллекционер платит не только за редкость\n\n"
        "Иногда главный фактор — история конкретного предмета и то, как его воспринимает узкая группа покупателей. "
        "Не пытайся свести каждую оценку к одной цифре. Сначала пойми, кто вообще готов это собирать и зачем"
    )
    decision = review_candidate(
        text=new_text,
        channel="gifts",
        topic="collector psychology",
        angle="identity and taste",
        format_key="story",
        history=[(old_fp, old_text)],
    )
    assert decision.similarity < .70
