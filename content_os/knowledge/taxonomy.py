from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeArea:
    key: str
    title: str
    terms: tuple[str, ...]


KNOWLEDGE_AREAS: tuple[KnowledgeArea, ...] = (
    KnowledgeArea("hooks", "Хуки", ("хук", "заголов", "первые секунд", "первые 3", "вниман", "scroll", "скрол")),
    KnowledgeArea("retention", "Удержание", ("удерж", "досмотр", "ритм", "интриг", "open loop", "пауза", "сценар")),
    KnowledgeArea("offers", "Офферы", ("оффер", "ценност", "результат", "обещан", "гарант", "бонус", "цена")),
    KnowledgeArea("cta", "CTA", ("cta", "призыв", "действ", "перейти", "написать", "заявк", "кнопк")),
    KnowledgeArea("funnels", "Воронки", ("ворон", "лид", "прогрев", "конверс", "трафик", "этап", "касани")),
    KnowledgeArea("sales", "Продажи", ("продаж", "возраж", "клиент", "созвон", "закрыт", "допрод", "upsell")),
    KnowledgeArea("telegram", "Telegram", ("telegram", "телеграм", "канал", "бот", "пост", "stories", "сторис", "premium")),
    KnowledgeArea("shorts", "Shorts / Reels", ("reels", "shorts", "рилс", "коротк видео", "ролик", "монтаж", "вертикал")),
    KnowledgeArea("positioning", "Позиционирование", ("позиционир", "аудитор", "сегмент", "целевая", "целевая аудит", "конкурент", "ниша")),
    KnowledgeArea("analytics", "Аналитика", ("аналит", "метрик", "тест", "гипотез", "переменн", "конверс", "данн")),
    KnowledgeArea("football", "Развитие футболиста", ("футбол", "игрок", "матч", "тренир", "позици", "техник", "тактик", "психолог")),
)


def classify_text(text: str, limit: int = 3) -> tuple[KnowledgeArea, ...]:
    lowered = (text or "").lower()
    ranked = []
    for area in KNOWLEDGE_AREAS:
        score = sum(lowered.count(term) for term in area.terms)
        if score:
            ranked.append((score, area))
    ranked.sort(key=lambda item: (-item[0], item[1].key))
    return tuple(area for _, area in ranked[:max(1, limit)])
