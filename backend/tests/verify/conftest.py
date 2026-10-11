import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.config import CameraConfig, Settings
from app.models import CandidateEvent


class FakeMessages:
    """Stands in for client.beta.messages: records the request, returns a canned reply."""

    def __init__(self, reply=None, error: Exception | None = None, delay: float = 0.0):
        self.reply, self.error, self.delay = reply, error, delay
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.reply


def fake_client(messages: FakeMessages) -> SimpleNamespace:
    return SimpleNamespace(beta=SimpleNamespace(messages=messages))


def text_reply(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason, stop_details=None, content=[SimpleNamespace(type="text", text=text)]
    )


@pytest.fixture
def camera() -> CameraConfig:
    return CameraConfig(
        id="CAM-02", name="Elmina Shoplot Row B", location="Jalan Limau Manis", clip="case-2.mp4",
        analyse=True, exits={"right": "Gate B"}, compass={"right": "east", "up": "north"},
    )


@pytest.fixture
def candidate() -> CandidateEvent:
    return CandidateEvent(
        camera_id="CAM-02", pts=6.4, loop=0, trigger="rule", suspect_track_ids=[16],
        victim_track_id=1, motorcycle_track_id=18, detected_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, anthropic_api_key="test-key", claude_model="claude-opus-5-5")


VALID_JSON = (
    '{"is_incident": true, "incident_type": "snatch_theft", "confidence": 0.93,'
    ' "summary": "Rider on a motorcycle snatched a bag from a woman and fled.",'
    ' "suspects": [{"track_id": 16, "description": "rider, dark helmet, white shirt"}],'
    ' "victim": {"track_id": 1, "description": "woman, pink top"},'
    ' "vehicle": {"type": "motorcycle", "colour": "black", "plate_visible": false, "plate_text": null},'
    ' "escape_direction": "east"}'
)
