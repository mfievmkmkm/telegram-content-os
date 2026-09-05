from content_os.preflight import build_preflight, missing_variable_names
from content_os.rollout import RolloutStage


def _editor_env():
    return {
        "BOT_TOKEN":"x","SUPABASE_URL":"x","SUPABASE_KEY":"x","LIGA_CHANNEL_ID":"x","GIFTS_CHANNEL_ID":"x","LLM_API_KEY":"x",
        "MPT_BASE_URL":"x","MPT_API_KEY":"x","CONTENT_OS_RUNTIME":"v2","AUTO_PUBLISH":"false",
    }


def _worker_env():
    return {
        "SHORTS_API_KEY":"x","PEXELS_API_KEY":"x","YANDEX_SPEECHKIT_API_KEY":"x","YANDEX_CLOUD_FOLDER_ID":"x","SHORTS_DATA_DIR":"/data",
    }


def test_preflight_blocks_when_ci_is_not_green():
    report=build_preflight(_editor_env(), _worker_env(), ci_green=False)
    assert not report.ready_for_live_smoke
    assert report.rollout.stage is RolloutStage.BLOCKED
    assert "CI must be green" in report.blocking


def test_preflight_moves_to_safe_smoke_when_env_and_ci_ready():
    report=build_preflight(_editor_env(), _worker_env(), ci_green=True)
    assert report.ready_for_live_smoke
    assert report.rollout.stage is RolloutStage.SAFE_SMOKE
    assert "boot" in report.rollout.allowed


def test_preflight_exposes_names_not_secret_values():
    env=_editor_env(); env["BOT_TOKEN"]=""
    report=build_preflight(env, _worker_env(), ci_green=True)
    assert "BOT_TOKEN" in missing_variable_names(report)
    assert "x" not in " ".join(report.blocking)
