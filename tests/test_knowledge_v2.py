from content_os.knowledge import KnowledgeQuery, build_playbook, classify_text, retrieve


def test_taxonomy_detects_hooks_and_sales():
    areas = {area.key for area in classify_text("Нужен сильный хук, CTA и продажа через Telegram", limit=5)}
    assert "hooks" in areas
    assert "sales" in areas or "cta" in areas


def test_retrieval_prefers_task_relevance_and_source_diversity():
    rows = [
        {"source_channel":"a","text":"Хук должен быстро обещать конкретный результат. Пример и правило для первых секунд."},
        {"source_channel":"a","text":"Ещё один материал про хук и первые секунды ролика."},
        {"source_channel":"a","text":"Третий почти такой же материал про хук."},
        {"source_channel":"b","text":"CTA должен продолжать обещание и давать понятное действие."},
        {"source_channel":"c","text":"Совсем другая тема про дизайн интерфейсов."},
    ]
    selected = retrieve(rows, KnowledgeQuery(task="сценарий Shorts: хук и CTA", areas=("hooks","cta"), limit=4))
    assert selected
    assert sum(1 for row in selected if row["source_channel"] == "a") <= 2
    assert any(row["source_channel"] == "b" for row in selected)


def test_playbook_does_not_claim_course_copying():
    rows = [{"source_channel":"course","text":"Правило: один эксперимент меняет одну переменную."}]
    playbook = build_playbook("проверить эксперимент", rows)
    assert "Не копируй" in playbook.prompt_context
    assert playbook.evidence
