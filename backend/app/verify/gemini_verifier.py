import asyncio
import json
from typing import Any

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.config import CameraConfig, Settings
from app.models import CandidateEvent, VerificationResult
from app.verify.base import VerificationUnavailable
from app.verify.claude_verifier import _strict_schema
from app.verify.prompt import build_prompt


class GeminiVerifier:
    def __init__(
        self,
        settings: Settings,
        client: genai.Client | None = None,
        timeout_s: float = 12.0,
    ):
        self.settings = settings
        self.timeout_s = timeout_s
        self.client = client or genai.Client(api_key=settings.gemini_api_key)
        self._schema = _strict_schema(VerificationResult)

    async def verify(
        self, candidate: CandidateEvent, keyframes: list[bytes], camera: CameraConfig
    ) -> VerificationResult:
        contents: list[Any] = [
            types.Part.from_bytes(data=frame, mime_type="image/jpeg") for frame in keyframes
        ]
        contents.append(build_prompt(candidate, camera))
        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=self._schema,
                        max_output_tokens=2000,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                ),
                timeout=self.timeout_s,
            )
        except asyncio.TimeoutError as exc:
            raise VerificationUnavailable(f"verification timed out after {self.timeout_s:g}s") from exc
        except errors.APIError as exc:
            raise VerificationUnavailable(f"Gemini API error: {exc}") from exc

        feedback = getattr(response, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            raise VerificationUnavailable(f"Gemini blocked the request ({feedback.block_reason})")
        text = response.text
        if not text:
            raise VerificationUnavailable("no content from Gemini")
        try:
            return VerificationResult.model_validate(json.loads(text))
        except (ValueError, ValidationError) as exc:
            raise VerificationUnavailable(f"response failed schema validation: {exc}") from exc
