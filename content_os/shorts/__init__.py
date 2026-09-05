"""Shorts Studio domain for staged, review-first video production.

The legacy VideoFactory remains available while the bot UI migrates to this
package. Keeping the boundary explicit lets us change script, voice, scenes or
captions independently without rebuilding unrelated stages.
"""

from .models import ShortBrief, ShortScene, ShortStage
from .presets import DELIVERY_PRESETS, VOICE_PRESETS, DeliveryPreset, VoicePreset

__all__ = [
    "ShortBrief",
    "ShortScene",
    "ShortStage",
    "DeliveryPreset",
    "VoicePreset",
    "DELIVERY_PRESETS",
    "VOICE_PRESETS",
]
