from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
import edge_tts


@dataclass(slots=True)
class TTSResult:
    provider: str
    alignment: dict[str, Any] | None = None
    warning: str = ""


class TTSProvider:
    name = "base"

    async def synthesize(self, text: str, path: Path, voice: str, speed: float) -> TTSResult:
        raise NotImplementedError


class ElevenLabsQuotaError(RuntimeError):
    """A recoverable billing state, not an authentication failure."""

    def __init__(self, remaining: int | None = None, required: int | None = None):
        self.remaining = remaining
        self.required = required
        if remaining is not None and required is not None:
            missing = max(0, required - remaining)
            message = (
                f"ElevenLabs: закончились кредиты — осталось {remaining}, нужно {required} "
                f"(не хватает {missing}). Сценарий сохранён"
            )
        else:
            message = "ElevenLabs: закончились кредиты. Сценарий сохранён"
        super().__init__(message)


class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"

    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip()

    @property
    def ready(self) -> bool:
        return bool(self.api_key and self.voice_id)

    async def synthesize(self, text: str, path: Path, voice: str, speed: float) -> TTSResult:
        if not self.ready:
            raise RuntimeError("ElevenLabs не настроен")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/with-timestamps"
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
        body = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.34,
                "similarity_boost": 0.78,
                "style": 0.48,
                "use_speaker_boost": True,
                "speed": max(.7, min(1.2, speed)),
            },
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
            async with session.post(url, params={"output_format": "mp3_44100_128"}, json=body, headers=headers) as response:
                if response.status >= 400:
                    response_text = await response.text()
                    code = ""
                    message = response_text
                    try:
                        detail = json.loads(response_text).get("detail") or {}
                        if isinstance(detail, dict):
                            code = str(detail.get("code") or "")
                            message = str(detail.get("message") or response_text)
                    except (ValueError, TypeError, AttributeError):
                        pass
                    if code == "quota_exceeded" or "quota" in message.lower():
                        remaining_match = re.search(r"(?:have|remaining)\D+(\d+)", message, re.I)
                        required_match = re.search(r"(?:while|need|required)\D+(\d+)", message, re.I)
                        raise ElevenLabsQuotaError(
                            int(remaining_match.group(1)) if remaining_match else None,
                            int(required_match.group(1)) if required_match else None,
                        )
                    if response.status in {401, 403}:
                        raise RuntimeError("ElevenLabs: ключ отклонён. Проверь ELEVENLABS_API_KEY и доступ к выбранному voice ID")
                    raise RuntimeError(f"ElevenLabs HTTP {response.status}: {message[:180]}")
                data = await response.json()
        path.write_bytes(base64.b64decode(data["audio_base64"]))
        return TTSResult(self.name, data.get("normalized_alignment") or data.get("alignment"))


class SpeechKitProvider(TTSProvider):
    name = "speechkit"
    # This worker currently calls SpeechKit REST API v1. Some newer voices
    # (for example anton/lera/marina) are v3-only in the current catalogue,
    # so legacy/editor voice names must resolve to voices that v1 accepts.
    VOICE_ALIASES = {
        "ru-ru-dmitryneural": "ermil",
        "ru-ru-svetlananeural": "jane",
        "ru-ru-dariyaneural": "alena",
        "anton": "ermil",
        "lera": "jane",
        "marina": "alena",
        "alexander": "zahar",
        "kirill": "filipp",
    }
    V1_VOICES = {"alena", "filipp", "ermil", "jane", "omazh", "zahar", "madi_ru"}

    def __init__(self):
        self.api_key = os.getenv("YANDEX_SPEECHKIT_API_KEY", "").strip()
        self.folder_id = os.getenv("YANDEX_CLOUD_FOLDER_ID", "").strip()

    @property
    def ready(self) -> bool:
        return bool(self.api_key and self.folder_id)

    @classmethod
    def normalize_voice(cls, voice: str) -> str:
        requested = (voice or "").strip()
        if not requested:
            return "jane"
        lowered = requested.lower()
        if lowered in cls.VOICE_ALIASES:
            return cls.VOICE_ALIASES[lowered]
        if lowered in cls.V1_VOICES:
            return lowered
        # Never forward Edge/Azure IDs or v3-only/unknown names to the v1
        # endpoint. Use a stable v1 Russian voice instead.
        return "jane"

    async def synthesize(self, text: str, path: Path, voice: str, speed: float) -> TTSResult:
        if not self.ready:
            raise RuntimeError("Yandex SpeechKit не настроен")
        headers = {"Authorization": f"Api-Key {self.api_key}"}
        data = {
            "text": text,
            "lang": "ru-RU",
            "voice": self.normalize_voice(voice),
            "speed": f"{max(.6, min(1.5, speed)):.2f}",
            "format": "mp3",
            "folderId": self.folder_id,
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120), headers=headers) as session:
            async with session.post("https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize", data=data) as response:
                if response.status >= 400:
                    raise RuntimeError(f"SpeechKit HTTP {response.status}: {(await response.text())[:180]}")
                path.write_bytes(await response.read())
        return TTSResult(self.name)


class EdgeProvider(TTSProvider):
    name = "edge"

    async def synthesize(self, text: str, path: Path, voice: str, speed: float) -> TTSResult:
        rate = f"{round((max(.7, min(1.4, speed)) - 1) * 100):+d}%"
        await edge_tts.Communicate(text, voice=voice or "ru-RU-DmitryNeural", rate=rate, pitch="+0Hz").save(str(path))
        return TTSResult(self.name)


class TTSRouter:
    """Select the requested provider and degrade only when policy explicitly allows it."""

    def __init__(self):
        self.providers = {
            "speechkit": SpeechKitProvider(),
            "elevenlabs": ElevenLabsProvider(),
            "edge": EdgeProvider(),
        }
        self.allow_edge_fallback = os.getenv("SHORTS_ALLOW_EDGE_FALLBACK", "false").lower() in {"1", "true", "yes", "on"}

    def health(self) -> dict[str, bool]:
        return {
            "speechkit": bool(getattr(self.providers["speechkit"], "ready", False)),
            "elevenlabs": bool(getattr(self.providers["elevenlabs"], "ready", False)),
            "edge": True,
        }

    async def synthesize(self, provider: str, text: str, path: Path, voice: str, speed: float) -> TTSResult:
        provider = (provider or "speechkit").strip().lower()
        if provider == "uploaded":
            raise RuntimeError("Своя озвучка должна быть загружена до запуска render")
        selected = self.providers.get(provider)
        if selected is None:
            raise RuntimeError(f"Неизвестный TTS provider: {provider}")
        try:
            return await selected.synthesize(text, path, voice, speed)
        except Exception as exc:
            if provider != "edge" and self.allow_edge_fallback:
                result = await self.providers["edge"].synthesize(text, path, "ru-RU-DmitryNeural", speed)
                result.warning = f"{provider} недоступен: {type(exc).__name__}: {str(exc)[:140]}"
                return result
            raise
