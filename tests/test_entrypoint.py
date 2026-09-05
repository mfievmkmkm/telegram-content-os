from content_os.entrypoint import runtime_name


def test_runtime_defaults_to_legacy(monkeypatch):
    monkeypatch.delenv("CONTENT_OS_RUNTIME", raising=False)
    assert runtime_name()=="legacy"


def test_runtime_enables_v2_explicitly(monkeypatch):
    monkeypatch.setenv("CONTENT_OS_RUNTIME","v2")
    assert runtime_name()=="v2"
