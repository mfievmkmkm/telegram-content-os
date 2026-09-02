import re

BORING = (
    "всем привет", "доброе утро", "сегодня мы", "давайте разбер", "в современном мире",
    "важно понимать", "ни для кого не секрет", "хотим рассказать", "рынок демонстрирует",
)
POWER = (
    "почему", "как", "никогда", "ошибка", "врёт", "мусор", "страх", "потерял",
    "уже", "тебя", "твой", "если", "пока", "вместо", "хуже", "ловушка",
)


def score_hook(text: str) -> tuple[int, list[str]]:
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    low, score, reasons = first.lower(), 0, []
    words = re.findall(r"[а-яёa-z0-9]+", low)
    if 3 <= len(words) <= 14: score += 2
    else: reasons.append("первая строка должна быть 3–14 слов")
    if any(x in low for x in POWER): score += 2
    else: reasons.append("нет конфликта, боли или интриги")
    if any(x in low for x in BORING): score -= 4; reasons.append("банальный нейросетевой заход")
    if len(first) > 90: score -= 1; reasons.append("хук слишком длинный")
    if first.endswith("."): score -= 1; reasons.append("хук звучит как обычное утверждение")
    return max(0, min(5, score)), reasons


def passes_hook_gate(text: str) -> bool:
    return score_hook(text)[0] >= 3

