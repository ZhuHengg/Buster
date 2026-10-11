from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.config import CameraConfig, Settings
from app.models import (
    CandidateEvent,
    EscalationStep,
    Incident,
    IncidentStatus,
    PersonDesc,
    VehicleDesc,
    VerificationResult,
)


class SpyService:
    """Records mark_escalation calls (stands in for IncidentService)."""

    def __init__(self):
        self.steps: list[EscalationStep] = []

    async def mark_escalation(self, incident_id: str, step: EscalationStep):
        self.steps.append(step)

    def statuses(self, channel: str) -> list[str]:
        return [s.status for s in self.steps if s.channel == channel]


@pytest.fixture
def spy() -> SpyService:
    return SpyService()


@pytest.fixture
def camera() -> CameraConfig:
    return CameraConfig(
        id="CAM-02", name="Elmina Shoplot Row B", location="Jalan Limau Manis", clip="case-2.mp4",
        analyse=True, exits={"right": "Gate B"}, compass={"right": "east"},
    )


def make_incident(status=IncidentStatus.APPROVED, verified: bool = True) -> Incident:
    detected = datetime(2026, 10, 11, 4, 5, tzinfo=timezone.utc)  # 12:05 in Malaysia (UTC+8)
    verification = VerificationResult(
        is_incident=True, incident_type="snatch_theft", confidence=0.93,
        summary="A rider on a black motorcycle snatched a bag from a woman and fled east.",
        suspects=[PersonDesc(track_id=16, description="rider in white shirt and dark helmet")],
        victim=PersonDesc(track_id=1, description="woman in pink top"),
        vehicle=VehicleDesc(type="motorcycle", colour="black", plate_visible=False, plate_text=None),
        escape_direction="east",
    ) if verified else None
    return Incident(
        id="INC-20261011-0001", camera_id="CAM-02", status=status,
        candidate=CandidateEvent(
            camera_id="CAM-02", pts=6.4, loop=0, trigger="rule", suspect_track_ids=[16],
            victim_track_id=1, motorcycle_track_id=18, detected_at=detected,
        ),
        verification=verification,
        verification_error=None if verified else "AI verification unavailable: timed out",
        escape_direction="east", escape_exit="Gate B", snapshot_files=[], clip_file="case-2.mp4",
        clip_start=2.4, clip_end=9.4, operator="Aina", created_at=detected,
    )


@pytest.fixture
def incident() -> Incident:
    return make_incident()


def full_settings(**over) -> Settings:
    base = dict(
        _env_file=None, twilio_account_sid="AC1", twilio_auth_token="tok", twilio_from_number="+15550001",
        police_number="+60123456789", gate_number="+60129876543",
    )
    base.update(over)
    return Settings(**base)


class FakeTwilio:
    """Minimal twilio.rest.Client double: calls.create / calls(sid).fetch / messages.create."""

    def __init__(self, call_statuses=("queued", "ringing", "completed"), sms_error: Exception | None = None):
        self.call_statuses = list(call_statuses)
        self.sms_error = sms_error
        self.created_calls: list[dict] = []
        self.sent: list[dict] = []
        self.fetches = 0
        outer = self

        class _Calls:
            def create(self, **kw):
                outer.created_calls.append(kw)
                return SimpleNamespace(sid="CA123", status="queued")

            def __call__(self, sid):
                assert sid == "CA123"

                def fetch():
                    i = min(outer.fetches, len(outer.call_statuses) - 1)
                    outer.fetches += 1
                    return SimpleNamespace(status=outer.call_statuses[i])

                return SimpleNamespace(fetch=fetch)

        class _Messages:
            def create(self, **kw):
                if outer.sms_error:
                    raise outer.sms_error
                outer.sent.append(kw)
                return SimpleNamespace(sid="SM1")

        self.calls = _Calls()
        self.messages = _Messages()
