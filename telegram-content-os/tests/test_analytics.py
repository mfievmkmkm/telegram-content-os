from types import SimpleNamespace

from content_os.analytics import reaction_count

def test_reactions_are_summed():
    message=SimpleNamespace(reactions=SimpleNamespace(results=[SimpleNamespace(count=3),SimpleNamespace(count=4)]))
    assert reaction_count(message)==7

def test_missing_reactions():
    assert reaction_count(SimpleNamespace(reactions=None))==0
