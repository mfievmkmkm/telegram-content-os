from content_os.entrypoint import runtime_name


def test_v2_is_the_safe_default(monkeypatch):
    monkeypatch.delenv("CONTENT_OS_RUNTIME", raising=False)
    assert runtime_name() == "v2"


def test_legacy_requires_explicit_rollback(monkeypatch):
    monkeypatch.setenv("CONTENT_OS_RUNTIME", "legacy")
    assert runtime_name() == "legacy"
