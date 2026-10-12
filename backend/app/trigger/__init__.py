import logging

from app.config import CameraConfig, Settings
from app.trigger.base import Trigger
from app.video.buffer import FrameBuffer

log = logging.getLogger(__name__)


def make_trigger(
    settings: Settings, camera: CameraConfig, buffer: FrameBuffer, blocking: bool = False
) -> Trigger:
    """Rule B, the Gemini screener, or both. Without a Gemini key it is always Rule B alone."""
    from app.trigger.snatch_rule import SnatchRule

    if settings.triggers != "rule" and not settings.gemini_api_key:
        log.warning("GEMINI_API_KEY is not set: using Rule B only for %s", camera.id)
        return SnatchRule()
    if settings.triggers == "rule":
        return SnatchRule()

    from app.trigger.gemini_trigger import GeminiTrigger

    gemini = GeminiTrigger(settings, camera, buffer, blocking=blocking)
    if settings.triggers == "llm":
        return gemini
    from app.trigger.any_trigger import AnyTrigger

    return AnyTrigger([SnatchRule(), gemini])
