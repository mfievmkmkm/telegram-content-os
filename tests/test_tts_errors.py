import sys
from types import SimpleNamespace

# The main application test environment does not install the worker-only Edge
# dependency; quota parsing itself does not need it.
sys.modules.setdefault("edge_tts", SimpleNamespace())

from shorts_service.tts import ElevenLabsQuotaError


def test_elevenlabs_quota_error_is_actionable_and_not_called_bad_key():
    error = ElevenLabsQuotaError(163, 477)
    assert "осталось 163" in str(error)
    assert "нужно 477" in str(error)
    assert "не хватает 314" in str(error)
    assert "ключ" not in str(error).lower()


def test_elevenlabs_quota_error_supports_changed_api_message():
    assert "закончились кредиты" in str(ElevenLabsQuotaError())
