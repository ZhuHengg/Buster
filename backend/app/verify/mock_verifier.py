from pathlib import Path

from app.config import CameraConfig, Settings
from app.models import (
    CandidateEvent,
    PersonDesc,
    VehicleDesc,
    VerificationResult,
)
from app.verify.base import Verifier
from app.verify.claude_verifier import ClaudeVerifier
from app.verify.gemini_verifier import GeminiVerifier


class MockVerifier:
    """Offline stand-in: returns data/mock_verifications/<camera_id>.json if present, else a canned snatch."""

    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = Path(fixtures_dir)

    async def verify(
        self, candidate: CandidateEvent, keyframes: list[bytes], camera: CameraConfig
    ) -> VerificationResult:
        fixture = self.fixtures_dir / f"{candidate.camera_id}.json"
        if fixture.exists():
            return VerificationResult.model_validate_json(fixture.read_text(encoding="utf-8"))
        suspects = [
            PersonDesc(track_id=tid, description="rider on motorcycle, helmet, dark clothing")
            for tid in candidate.suspect_track_ids
        ] or [PersonDesc(track_id=None, description="rider on motorcycle, helmet, dark clothing")]
        return VerificationResult(
            is_incident=True,
            incident_type="snatch_theft",
            confidence=0.9,
            summary="A motorcycle rider grabbed a bag from a pedestrian and rode away.",
            suspects=suspects,
            victim=PersonDesc(track_id=candidate.victim_track_id, description="pedestrian"),
            vehicle=VehicleDesc(type="motorcycle", colour="dark", plate_visible=False, plate_text=None),
            escape_direction="unknown",
        )


def make_verifier(settings: Settings) -> Verifier:
    if settings.gemini_api_key:
        return GeminiVerifier(settings)
    if settings.anthropic_api_key:
        return ClaudeVerifier(settings)
    return MockVerifier(settings.data_dir / "mock_verifications")
