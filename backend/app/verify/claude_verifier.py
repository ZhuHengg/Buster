import asyncio
import base64
import json
from typing import Any

import anthropic
from pydantic import ValidationError

from app.config import CameraConfig, Settings
from app.models import CandidateEvent, VerificationResult
from app.verify.base import VerificationUnavailable
from app.verify.prompt import build_prompt

FALLBACK_BETA = "server-side-fallback-2026-07-01"
_DROP_KEYS = {"title", "default", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}


def _strict_schema(model: type) -> dict[str, Any]:
    """JSON schema for structured outputs: refs inlined, additionalProperties false, no numeric bounds.

    Bounds (confidence 0..1) are enforced afterwards by pydantic validation.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return walk(defs[node["$ref"].split("/")[-1]])
        out = {k: walk(v) for k, v in node.items() if k not in _DROP_KEYS}
        if out.get("type") == "object":
            out["additionalProperties"] = False
            out["required"] = list(out.get("properties", {}))
        return out

    return walk(schema)


class ClaudeVerifier:
    def __init__(
        self,
        settings: Settings,
        client: anthropic.AsyncAnthropic | None = None,
        timeout_s: float = 12.0,
    ):
        self.settings = settings
        self.timeout_s = timeout_s
        self.client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key, max_retries=0
        )
        self._schema = _strict_schema(VerificationResult)

    async def verify(
        self, candidate: CandidateEvent, keyframes: list[bytes], camera: CameraConfig
    ) -> VerificationResult:
        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(frame).decode("ascii"),
                },
            }
            for frame in keyframes
        ]
        content.append({"type": "text", "text": build_prompt(candidate, camera)})
        try:
            response = await asyncio.wait_for(
                self.client.beta.messages.create(
                    model=self.settings.claude_model,
                    max_tokens=2000,
                    betas=[FALLBACK_BETA],
                    fallbacks="default",
                    output_config={
                        "effort": "low",
                        "format": {"type": "json_schema", "schema": self._schema},
                    },
                    messages=[{"role": "user", "content": content}],
                ),
                timeout=self.timeout_s,
            )
        except asyncio.TimeoutError as exc:
            raise VerificationUnavailable(f"verification timed out after {self.timeout_s:g}s") from exc
        except anthropic.APIError as exc:
            raise VerificationUnavailable(f"Claude API error: {exc}") from exc

        if response.stop_reason == "refusal":
            raise VerificationUnavailable("Claude refused the request")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise VerificationUnavailable(f"no content (stop_reason={response.stop_reason})")
        try:
            return VerificationResult.model_validate(json.loads(text))
        except (ValueError, ValidationError) as exc:
            raise VerificationUnavailable(f"response failed schema validation: {exc}") from exc
