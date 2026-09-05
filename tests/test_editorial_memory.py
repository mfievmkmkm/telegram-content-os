from content_os.content_quality import build_fingerprint
from content_os.editorial_memory import EditorialMemory


class MemoryDB:
    def __init__(self): self.data = {}
    def get(self, key): return self.data.get(key)
    def set(self, key, value): self.data[key] = value


def test_editorial_memory_roundtrip():
    db = MemoryDB(); memory = EditorialMemory(db)
    fp = build_fingerprint(text="Ошибка начинается раньше", topic="decision", angle="before touch", format_key="story")
    memory.remember_content("liga", fp, "Ошибка начинается раньше", draft_id=4)
    rows = memory.fingerprints("liga")
    assert len(rows) == 1
    assert rows[0][0].topic == "decision"
    assert rows[0][1] == "Ошибка начинается раньше"


def test_visual_memory_and_variant():
    db = MemoryDB(); memory = EditorialMemory(db)
    for key in ("tunnel", "tactics", "training"):
        memory.remember_visual("liga", key)
    assert memory.recent_visuals("liga")[-2:] == ["tactics", "training"]
    assert memory.selected_variant(7) is None
    memory.select_variant(7, 2)
    assert memory.selected_variant(7) == 2
    memory.select_variant(7, 7)
    assert memory.selected_variant(7) == 7
