import asyncio

from content_os.director_service import ContentDirectorService


class Row(dict):
    __getattr__ = dict.get


class MemoryDB:
    def __init__(self):
        self.settings = {}
        self.rows = {
            1: Row(id=1, channel_key="gifts", format_key="guide", text="В современном мире важно понимать рынок", hook_score=1, source_title="market")
        }
    def get(self, key): return self.settings.get(key)
    def set(self, key, value): self.settings[key] = value
    def draft(self, draft_id): return self.rows.get(draft_id)
    def update(self, draft_id, **fields): self.rows[draft_id].update(fields)
    def style_examples(self, channel, limit=12): return []


class Editor:
    async def rewrite(self, draft, mode):
        return (
            "Эта ошибка стоит дороже красивого floor\n\n"
            "Сначала проверь, что именно ты покупаешь, и только потом сравнивай цену. "
            "Одна цифра без контекста не объясняет ценность предмета и не заменяет проверку деталей. "
            "Если сомневаешься, собери факты и не спеши с выводом",
            4,
        )


def test_director_polishes_failed_draft():
    db = MemoryDB(); service = ContentDirectorService(Editor(), db)
    result = asyncio.run(service.polish(1))
    assert result.rewrites >= 1
    assert "современном мире" not in result.draft["text"].lower()
    service.remember(result)
    assert db.get("v2:fingerprints:gifts")
