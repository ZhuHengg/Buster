import time
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors

from app.config import CameraConfig, Settings
from app.trigger.gemini_screener import GeminiScreener, ScreenUnavailable, build_screen_prompt

FRAMES = [b"\xff\xd8jpeg-%d" % i for i in range(6)]

POSITIVE = (
    '{"suspicious": true, "score": 0.82, "reason": "rider grabs bag and speeds off",'
    ' "suspect_track_ids": [16], "motorcycle_track_id": 18, "victim_track_id": 1}'
)


class FakeModels:
    def __init__(self, text=POSITIVE, error: Exception | None = None, delay: float = 0.0, block=None):
        self.text, self.error, self.delay, self.block = text, error, delay, block
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text, prompt_feedback=SimpleNamespace(block_reason=self.block))


def client_for(models: FakeModels) -> SimpleNamespace:
    return SimpleNamespace(models=models)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, gemini_api_key="k", gemini_model="gemini-2.5-flash")


@pytest.fixture
def camera() -> CameraConfig:
    return CameraConfig(id="CAM-02", name="Elmina Shoplot Row B", location="Jalan Limau Manis")


def test_screen_parses_result(settings, camera):
    result = GeminiScreener(settings, client=client_for(FakeModels())).screen(FRAMES, camera)
    assert result.suspicious is True
    assert result.score == pytest.approx(0.82)
    assert result.suspect_track_ids == [16]
    assert result.motorcycle_track_id == 18 and result.victim_track_id == 1


def test_screen_sends_one_image_part_per_frame_and_prompt_last(settings, camera):
    fake = FakeModels()
    GeminiScreener(settings, client=client_for(fake)).screen(FRAMES, camera)
    req = fake.calls[0]
    assert req["model"] == "gemini-2.5-flash"
    assert len(req["contents"]) == 7
    assert req["contents"][0].inline_data.mime_type == "image/jpeg"
    prompt = req["contents"][-1]
    assert "Elmina Shoplot Row B" in prompt and "plausible" in prompt
    assert req["config"].response_mime_type == "application/json"


def test_screen_uses_screen_model_when_set():
    s = Settings(_env_file=None, gemini_api_key="k", gemini_model="a", gemini_screen_model="b-lite")
    fake = FakeModels()
    GeminiScreener(s, client=client_for(fake)).screen(FRAMES, CameraConfig(id="C", name="n", location="l"))
    assert fake.calls[0]["model"] == "b-lite"


def test_screen_timeout_raises_screen_unavailable(settings, camera):
    fake = FakeModels(error=httpx.ReadTimeout("read timed out"))
    with pytest.raises(ScreenUnavailable, match="timed out"):
        GeminiScreener(settings, client=client_for(fake)).screen(FRAMES, camera)


def test_screen_transport_error_raises_screen_unavailable(settings, camera):
    fake = FakeModels(error=httpx.ConnectError("no route"))
    with pytest.raises(ScreenUnavailable, match="Gemini call failed"):
        GeminiScreener(settings, client=client_for(fake)).screen(FRAMES, camera)


def test_client_is_built_with_an_http_timeout(settings, monkeypatch):
    seen = {}

    class Recorder:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr("app.trigger.gemini_screener.genai.Client", Recorder)
    GeminiScreener(settings, timeout_s=8.0)
    assert seen["http_options"].timeout == 8000


def test_screen_api_error_raises_screen_unavailable(settings, camera):
    err = errors.APIError(429, {"error": {"message": "quota"}})
    with pytest.raises(ScreenUnavailable, match="Gemini API error"):
        GeminiScreener(settings, client=client_for(FakeModels(error=err))).screen(FRAMES, camera)


def test_screen_blocked_prompt_raises_screen_unavailable(settings, camera):
    fake = FakeModels(text=None, block="SAFETY")
    with pytest.raises(ScreenUnavailable, match="blocked"):
        GeminiScreener(settings, client=client_for(fake)).screen(FRAMES, camera)


def test_screen_bad_json_raises_screen_unavailable(settings, camera):
    with pytest.raises(ScreenUnavailable, match="schema"):
        GeminiScreener(settings, client=client_for(FakeModels(text="not json"))).screen(FRAMES, camera)


def test_score_above_one_is_schema_failure(settings, camera):
    bad = POSITIVE.replace('"score": 0.82', '"score": 1.7')
    with pytest.raises(ScreenUnavailable, match="schema"):
        GeminiScreener(settings, client=client_for(FakeModels(text=bad))).screen(FRAMES, camera)


def test_prompt_mentions_camera_context(camera):
    prompt = build_screen_prompt(camera)
    assert "Jalan Limau Manis" in prompt and "reviewer" in prompt
