from content_os.system_health import blocking_subsystems, subsystem_statuses


def env():
    return {
        "BOT_TOKEN":"x","LLM_API_KEY":"x","LIGA_CHANNEL_ID":"x","GIFTS_CHANNEL_ID":"x",
        "SUPABASE_URL":"x","SUPABASE_KEY":"x","MPT_BASE_URL":"x","MPT_API_KEY":"x",
        "SHORTS_API_KEY":"x","PEXELS_API_KEY":"x","YANDEX_SPEECHKIT_API_KEY":"x","YANDEX_CLOUD_FOLDER_ID":"x",
        "PUBLISH_VIA_MTPROTO":"false",
    }


def test_core_subsystems_ready_without_exposing_values():
    statuses=subsystem_statuses(env())
    assert not blocking_subsystems(env())
    assert all("x" not in item.missing for item in statuses)


def test_missing_worker_secret_is_blocking():
    data=env(); data.pop("YANDEX_CLOUD_FOLDER_ID")
    blocked={item.key:item for item in blocking_subsystems(data)}
    assert "shorts_worker" in blocked
    assert blocked["shorts_worker"].missing == ("YANDEX_CLOUD_FOLDER_ID",)


def test_optional_systems_are_not_release_blockers():
    data=env()
    statuses={item.key:item for item in subsystem_statuses(data)}
    assert statuses["shop"].ready
    assert statuses["matchlens"].ready
    assert statuses["premium_publish"].ready
