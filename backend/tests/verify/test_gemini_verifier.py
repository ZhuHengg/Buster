import asyncio
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.config import Settings
from app.verify.base import VerificationUnavailable
from app.verify.gemini_verifier import GeminiVerifier
from tests.verify.conftest import VALID_JSON

FRAMES = [b"\xff\xd8jpeg-bytes-%d" % i for i in range(8)]


class FakeModels:
    def __init__(self, text=VALID_JSON, error: Exception | None = None, delay: float = 0.0, block=None):
        self.text, self.error, self.delay, self.block = text, error, delay, block
        self.calls: list[dict] = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text, prompt_feedback=SimpleNamespace(block_reason=self.block))


def client_for(models: FakeModels) -> SimpleNamespace:
    return SimpleNamespace(aio=SimpleNamespace(models=models))


@pytest.fixture
def gemini_settings() -> Settings:
    return Settings(_env_file=None, gemini_api_key="test-key", gemini_model="gemini-2.5-flash")


async def test_gemini_verifier_parses_structured_result(gemini_settings, camera, candidate):
    result = await GeminiVerifier(gemini_settings, client=client_for(FakeModels())).verify(
        candidate, FRAMES, camera
    )
    assert result.is_incident is True
    assert result.incident_type == "snatch_theft"
    assert result.suspects[0].track_id == 16


async def test_gemini_verifier_sends_images_prompt_and_schema(gemini_settings, camera, candidate):
    fake = FakeModels()
    await GeminiVerifier(gemini_settings, client=client_for(fake)).verify(candidate, FRAMES, camera)
    req = fake.calls[0]
    assert req["model"] == "gemini-2.5-flash"
    assert len(req["contents"]) == 9  # 8 images, prompt last
    assert req["contents"][0].inline_data.mime_type == "image/jpeg"
    assert "Elmina Shoplot Row B" in req["contents"][-1]
    assert req["config"].response_mime_type == "application/json"
    assert req["config"].response_json_schema["type"] == "object"


async def test_gemini_verifier_timeout_raises_unavailable(gemini_settings, camera, candidate):
    verifier = GeminiVerifier(gemini_settings, client=client_for(FakeModels(delay=1.0)), timeout_s=0.05)
    with pytest.raises(VerificationUnavailable, match="timed out"):
        await verifier.verify(candidate, FRAMES, camera)


async def test_gemini_verifier_api_error_raises_unavailable(gemini_settings, camera, candidate):
    err = errors.APIError(500, {"error": {"message": "boom"}})
    with pytest.raises(VerificationUnavailable, match="Gemini API error"):
        await GeminiVerifier(gemini_settings, client=client_for(FakeModels(error=err))).verify(
            candidate, FRAMES, camera
        )


async def test_gemini_verifier_blocked_raises_unavailable(gemini_settings, camera, candidate):
    fake = FakeModels(text=None, block="SAFETY")
    with pytest.raises(VerificationUnavailable, match="blocked"):
        await GeminiVerifier(gemini_settings, client=client_for(fake)).verify(candidate, FRAMES, camera)


async def test_gemini_verifier_schema_failure_raises_unavailable(gemini_settings, camera, candidate):
    fake = FakeModels(text='{"is_incident": true}')
    with pytest.raises(VerificationUnavailable, match="schema"):
        await GeminiVerifier(gemini_settings, client=client_for(fake)).verify(candidate, FRAMES, camera)


def test_verification_prompt_rejects_aftermath_and_never_names_helpers_as_suspects():
    from datetime import datetime, timezone

    from app.config import CameraConfig
    from app.models import CandidateEvent
    from app.verify.prompt import build_prompt

    cand = CandidateEvent(camera_id="C", pts=1.0, loop=0, trigger="llm", suspect_track_ids=[], detected_at=datetime.now(timezone.utc))
    p = build_prompt(cand, CameraConfig(id="C", name="n", location="l")).lower()
    assert "aftermath" in p and "is_incident false" in p
    assert "helping" in p and "never" in p
