from content_os.release_gate import evaluate_release


def base_env():
    return {
        "BOT_TOKEN": "x", "SUPABASE_URL": "x", "SUPABASE_KEY": "x",
        "LIGA_CHANNEL_ID": "x", "GIFTS_CHANNEL_ID": "x", "LLM_API_KEY": "x",
        "SHORTS_WORKER_URL": "x", "YANDEX_SPEECHKIT_API_KEY": "x",
    }


def test_release_gate_fails_closed_on_missing_secret():
    env = base_env(); env.pop("BOT_TOKEN")
    result = evaluate_release(env)
    assert not result.ready
    assert "missing:BOT_TOKEN" in result.blocking


def test_release_gate_never_requires_secret_values_to_be_exposed():
    result = evaluate_release(base_env())
    assert result.ready
    assert result.blocking == ()


def test_rollout_warnings_are_non_blocking():
    env = base_env() | {"AUTO_PUBLISH": "true", "SHORTS_ALLOW_EDGE_FALLBACK": "true"}
    result = evaluate_release(env)
    assert result.ready
    assert "publishing:auto_publish_enabled_during_rollout" in result.warnings
    assert "shorts:edge_fallback_enabled" in result.warnings
