from content_os.knowledge.guidance import guidance_for_task


def test_guidance_retrieves_practical_material_without_promoting_it_to_fact_pack():
    rows = [
        {"text": "Правило: сильный хук должен быстро показать конфликт и удержать внимание", "source_channel": "content"},
        {"text": "Чеклист оффера: результат, срок, усилия, риск", "source_channel": "sales"},
        {"text": "нерелевантная заметка про сад", "source_channel": "other"},
    ]
    result = guidance_for_task(rows, "сделать сильный хук для короткого поста", "gifts")
    assert result.playbook.evidence
    assert "не как источник текущих фактов" in result.prompt_context.lower()
    assert "fact pack" in result.prompt_context.lower()


def test_guidance_is_safe_when_library_has_no_matching_rows():
    result = guidance_for_task([], "shorts retention", "liga")
    assert result.playbook.evidence == ()
    assert "не обещай результат" in result.prompt_context.lower()
