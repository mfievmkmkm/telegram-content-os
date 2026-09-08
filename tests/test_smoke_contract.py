from content_os.smoke_contract import SMOKE_STEPS, remaining, safe_phase


def test_smoke_contract_has_unique_stable_keys():
    keys=[step.key for step in SMOKE_STEPS]
    assert len(keys) == len(set(keys))
    assert {"boot","draft","shorts_render","growth","sales","restart"}.issubset(keys)


def test_safe_phase_never_contains_external_write_steps():
    assert all(not step.destructive for step in safe_phase())
    assert "publish_private" not in {step.key for step in safe_phase()}


def test_remaining_tracks_progress():
    left=remaining({"boot","home"})
    assert "boot" not in {step.key for step in left}
    assert "draft" in {step.key for step in left}
