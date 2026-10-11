from typing import Protocol

from app.config import CameraConfig
from app.models import CandidateEvent, VerificationResult


class VerificationUnavailable(Exception):
    """Step 2 could not produce a verdict (timeout, network error, refusal, bad schema)."""


class Verifier(Protocol):
    async def verify(
        self, candidate: CandidateEvent, keyframes: list[bytes], camera: CameraConfig
    ) -> VerificationResult: ...
