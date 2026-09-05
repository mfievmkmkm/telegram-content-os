from content_os.release_gate import evaluate_release, evaluate_shorts_worker


def editor_env():
    return {
        "BOT_TOKEN": "x", "SUPABASE_URL": "x", "SUPABASE_KEY": "x",
        "LIGA_CHANNEL_ID": "x", "GIFTS_CHANNEL_ID": "x", "LLM_API_KEY": "x",
        "MPT_BASE_URL": "https://shorts.example", "MPT_API_KEY": "x",
    }


def worker_env():
    return {
        "SHORTS_API_KEY": "x", "PEXELS_API_KEY": "x",
        "YANDEX_SPEECHKIT_API_KEY": "x", "YANDEX_CLOUD_FOLDER_ID": "x",
        "SHORTS_DATA_DIR": "/data",
    }


def test_editor_release_gate_fails_closed_on_missing_secret():
    env = editor_env(); env.pop("BOT_TOKEN")
    result = evaluate_release(env)
    assert not result.ready
    assert "missing:BOT_TOKEN" in result.blocking


def test_editor_requires_worker_connection_not_worker_secrets():
    result = evaluate_release(editor_env())
    assert result.ready
    assert "missing:YANDEX_SPEECHKIT_API_KEY" not in result.blocking


def test_worker_gate_blocks_incomplete_speechkit():
    env = worker_env(); env.pop("YANDEX_CLOUD_FOLDER_ID")
    result = evaluate_shorts_worker(env)
    assert not result.ready
    assert "missing:YANDEX_CLOUD_FOLDER_ID" in result.blocking


def test_worker_warns_about_edge_fallback_and_nonpersistent_dir():
    env = worker_env() | {"SHORTS_ALLOW_EDGE_FALLBACK": "true", "SHORTS_DATA_DIR": "/tmp/shorts"}
    result = evaluate_shorts_worker(env)
    assert result.ready
    assert "shorts:edge_fallback_enabled" in result.warnings
    assert "shorts:persistence_not_on_data_volume" in result.warnings


def test_rollout_warnings_are_non_blocking():
    env = editor_env() | {"AUTO_PUBLISH": "true"}
    result = evaluate_release(env)
    assert result.ready
    assert "publishing:auto_publish_enabled_during_rollout" in result.warnings
    assert "sales:shop_bot_disabled" in result.warnings
