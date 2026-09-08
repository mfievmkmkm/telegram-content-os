from pathlib import Path


def test_legacy_runtime_was_not_replaced_by_v2_migration():
    path = Path("content_os/__main__.py")
    text = path.read_text("utf-8")
    assert path.stat().st_size > 70_000
    assert text.startswith("import asyncio")
    assert "async def generate(" in text
    assert "async def publish(" in text


def test_root_entrypoint_is_fail_safe_legacy_by_default():
    text = Path("content_os/entrypoint.py").read_text("utf-8")
    assert 'or "legacy"' in text
    assert 'if runtime_name() == "v2"' in text
    docker = Path("Dockerfile").read_text("utf-8")
    assert "content_os.entrypoint" in docker


def test_env_examples_contain_placeholders_not_secret_values():
    root = Path(".env.example").read_text("utf-8")
    worker = Path("shorts_service/.env.example").read_text("utf-8")
    for line in (root + "\n" + worker).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if any(word in key for word in ("TOKEN", "KEY", "HASH", "SESSION")):
            # Public/default config values are allowed only for non-secret settings.
            assert not value.strip(), f"secret-like variable {key} must stay empty in examples"


def test_no_duplicate_workflow_directory_with_trailing_space():
    assert not Path(".github/workflows ").exists()
