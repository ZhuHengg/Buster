import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError

from app.config import CameraConfig, Settings
from app.verify.claude_verifier import _strict_schema


class ScreenUnavailable(Exception):
    """The screening call failed; the caller should back off, not crash."""


class ScreenResult(BaseModel):
    suspicious: bool
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    suspect_track_ids: list[int]
    motorcycle_track_id: int | None = None
    victim_track_id: int | None = None


def build_screen_prompt(camera: CameraConfig) -> str:
    return (
        f"You are screening CCTV footage from camera '{camera.name}' ({camera.location}).\n"
        "The images are consecutive frames, oldest first, covering about 3 seconds. They may or may "
        "not have numbered boxes (#id) drawn on people and motorcycles.\n"
        "Decide whether a snatch theft is happening or has just happened: a person, usually on a "
        "motorcycle, grabs a bag, phone or chain from a pedestrian and rides or runs away.\n"
        "Answer suspicious=true whenever this is plausible. A second reviewer removes false alarms, "
        "so a missed theft is worse than a false alarm.\n"
        "Normal traffic, people walking, parking, a rider stopping to talk, and people handing "
        "things to each other are not suspicious.\n"
        "score is your confidence from 0 to 1. Copy suspect, motorcycle and victim track ids from "
        "the visible #id labels only; leave the lists empty and the ids null if no labels are visible.\n"
        "reason is one short sentence."
    )


class GeminiScreener:
    def __init__(
        self,
        settings: Settings,
        client: genai.Client | None = None,
        timeout_s: float = 8.0,
    ):
        self.model = settings.gemini_screen_model or settings.gemini_model
        self.timeout_s = timeout_s
        self.client = client or genai.Client(api_key=settings.gemini_api_key)
        self._schema = _strict_schema(ScreenResult)
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gemini-screen")

    def screen(self, frames: list[bytes], camera: CameraConfig) -> ScreenResult:
        contents: list[Any] = [types.Part.from_bytes(data=f, mime_type="image/jpeg") for f in frames]
        contents.append(build_screen_prompt(camera))
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=self._schema,
            max_output_tokens=500,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        future = self._pool.submit(
            self.client.models.generate_content, model=self.model, contents=contents, config=config
        )
        try:
            response = future.result(timeout=self.timeout_s)
        except FutureTimeout as exc:
            raise ScreenUnavailable(f"screening timed out after {self.timeout_s:g}s") from exc
        except errors.APIError as exc:
            raise ScreenUnavailable(f"Gemini API error: {exc}") from exc

        feedback = getattr(response, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            raise ScreenUnavailable(f"Gemini blocked the request ({feedback.block_reason})")
        text = response.text
        if not text:
            raise ScreenUnavailable("no content from Gemini")
        try:
            return ScreenResult.model_validate(json.loads(text))
        except (ValueError, ValidationError) as exc:
            raise ScreenUnavailable(f"response failed schema validation: {exc}") from exc
