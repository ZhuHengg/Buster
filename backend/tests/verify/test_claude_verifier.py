import anthropic
import httpx2
import pytest

from app.verify.base import VerificationUnavailable
from app.verify.claude_verifier import ClaudeVerifier
from tests.verify.conftest import VALID_JSON, FakeMessages, fake_client, text_reply

FRAMES = [b"\xff\xd8jpeg-bytes-%d" % i for i in range(8)]


async def test_claude_verifier_parses_structured_result(settings, camera, candidate):
    fake = FakeMessages(reply=text_reply(VALID_JSON))
    result = await ClaudeVerifier(settings, client=fake_client(fake)).verify(candidate, FRAMES, camera)
    assert result.is_incident is True
    assert result.incident_type == "snatch_theft"
    assert result.confidence == pytest.approx(0.93)
    assert result.suspects[0].track_id == 16
    assert result.escape_direction == "east"


async def test_claude_verifier_sends_n_images_and_camera_context(settings, camera, candidate):
    fake = FakeMessages(reply=text_reply(VALID_JSON))
    await ClaudeVerifier(settings, client=fake_client(fake)).verify(candidate, FRAMES, camera)
    req = fake.calls[0]
    assert req["model"] == settings.claude_model
    content = req["messages"][0]["content"]
    images = [b for b in content if b["type"] == "image"]
    texts = [b for b in content if b["type"] == "text"]
    assert len(images) == 8
    assert images[0]["source"]["type"] == "base64"
    assert images[0]["source"]["media_type"] == "image/jpeg"
    assert content[-1]["type"] == "text"  # images first, prompt last
    assert "Elmina Shoplot Row B" in texts[0]["text"] and "Jalan Limau Manis" in texts[0]["text"]
    assert req["output_config"]["effort"] == "low"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert req["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in req["betas"]


async def test_claude_verifier_timeout_raises_unavailable(settings, camera, candidate):
    fake = FakeMessages(reply=text_reply(VALID_JSON), delay=1.0)
    verifier = ClaudeVerifier(settings, client=fake_client(fake), timeout_s=0.05)
    with pytest.raises(VerificationUnavailable, match="timed out"):
        await verifier.verify(candidate, FRAMES, camera)


async def test_claude_verifier_refusal_raises_unavailable(settings, camera, candidate):
    fake = FakeMessages(reply=text_reply("", stop_reason="refusal"))
    with pytest.raises(VerificationUnavailable, match="refus"):
        await ClaudeVerifier(settings, client=fake_client(fake)).verify(candidate, FRAMES, camera)


async def test_claude_verifier_api_error_raises_unavailable(settings, camera, candidate):
    err = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))
    fake = FakeMessages(error=err)
    with pytest.raises(VerificationUnavailable):
        await ClaudeVerifier(settings, client=fake_client(fake)).verify(candidate, FRAMES, camera)


async def test_claude_verifier_schema_failure_raises_unavailable(settings, camera, candidate):
    fake = FakeMessages(reply=text_reply('{"is_incident": true}'))
    with pytest.raises(VerificationUnavailable, match="schema"):
        await ClaudeVerifier(settings, client=fake_client(fake)).verify(candidate, FRAMES, camera)


async def test_claude_verifier_confidence_above_one_is_schema_failure(settings, camera, candidate):
    bad = VALID_JSON.replace('"confidence": 0.93', '"confidence": 1.7')
    fake = FakeMessages(reply=text_reply(bad))
    with pytest.raises(VerificationUnavailable):
        await ClaudeVerifier(settings, client=fake_client(fake)).verify(candidate, FRAMES, camera)
