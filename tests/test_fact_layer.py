from content_os.creative_director import inspect_content
from content_os.fact_layer import FactPack, FactStore, numeric_claims


class MemoryDB:
    def __init__(self): self.data={}
    def get(self,key): return self.data.get(key)
    def set(self,key,value): self.data[key]=value


def test_numeric_claims_are_normalized_for_comparison():
    assert numeric_claims("Цена 4,20 TON и рост +18%") == ("4.20TON", "+18%")


def test_gifts_numbers_without_fact_pack_are_blocked():
    report=inspect_content("Ошибка рынка\n\nЦена уже 4.2 TON, и это якобы рост. Проверь историю перед покупкой, иначе красивый экран снова окажется дороже здравого смысла.",channel="gifts")
    assert not report.approved
    assert any(issue.code=="facts_required" and issue.severity=="block" for issue in report.issues)


def test_only_numbers_present_in_fact_pack_are_allowed():
    text="Рынок дёрнулся\n\nЦена 4.2 TON видна во входных данных. Это ещё не доказывает спрос или будущий рост, поэтому сначала проверь реальные сделки и только потом принимай решение."
    allowed=inspect_content(text,channel="gifts",fact_numbers=("4.2TON",))
    invented=inspect_content(text.replace("4.2 TON","9 TON"),channel="gifts",fact_numbers=("4.2TON",))
    assert not any(issue.code=="unsupported_fact" for issue in allowed.issues)
    assert any(issue.code=="unsupported_fact" for issue in invented.issues)


def test_fact_store_preserves_source_and_timestamp():
    db=MemoryDB(); store=FactStore(db); store.save(7,FactPack.create("4 TON","Market API"))
    loaded=store.load(7)
    assert loaded and loaded.source=="Market API" and loaded.numbers==("4TON",)
