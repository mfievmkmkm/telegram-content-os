from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeliveryPreset:
    key: str
    title: str
    instruction: str
    target_words: tuple[int, int] = (48, 62)


@dataclass(frozen=True, slots=True)
class VoicePreset:
    key: str
    title: str
    provider: str
    voice: str
    speed: float
    channels: tuple[str, ...] = ("gifts", "liga")
    enabled_by_default: bool = True


DELIVERY_PRESETS = {
    "punchy": DeliveryPreset("punchy", "🔥 Дерзко", "Коротко, уверенно, с конфликтом. Без крика и дешёвой псевдодрамы."),
    "calm": DeliveryPreset("calm", "🧠 Спокойно", "Уверенный спокойный темп. Конкретика важнее эмоции."),
    "meme": DeliveryPreset("meme", "😂 Мемно", "Узнаваемая ситуация, сухой панч, лёгкий абсурд. Не превращай текст в набор шуток."),
    "sport": DeliveryPreset("sport", "⚽ Спортивно", "Энергия тренера и игрока: действие, решение, конкретная ошибка и практический вывод."),
}

# Provider names are stable domain identifiers. Actual credentials/voice IDs stay
# in Railway environment variables and are resolved by the Shorts Worker.
VOICE_PRESETS = {
    "auto_ru": VoicePreset("auto_ru", "🇷🇺 Авто · русский", "speechkit", "lera", 1.06),
    "ru_lera": VoicePreset("ru_lera", "Lera · энергично", "speechkit", "lera", 1.06),
    "ru_marina": VoicePreset("ru_marina", "Marina · уверенно", "speechkit", "marina", 1.02),
    "ru_anton": VoicePreset("ru_anton", "Anton · энергично", "speechkit", "anton", 1.05),
    "ru_kirill": VoicePreset("ru_kirill", "Kirill · нейтрально", "speechkit", "kirill", 1.02),
    "elevenlabs": VoicePreset("elevenlabs", "💎 ElevenLabs", "elevenlabs", "configured", 1.04),
    "uploaded": VoicePreset("uploaded", "🎙 Своя озвучка", "uploaded", "uploaded", 1.0),
}


def delivery(key: str) -> DeliveryPreset:
    return DELIVERY_PRESETS.get(key, DELIVERY_PRESETS["punchy"])


def voice(key: str) -> VoicePreset:
    return VOICE_PRESETS.get(key, VOICE_PRESETS["auto_ru"])
