from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import (
    CandidateEvent,
    EscalationStep,
    Incident,
    IncidentStatus,
    InvalidTransition,
    PersonDesc,
    VehicleDesc,
    VerificationResult,
    transition,
)

S = IncidentStatus

ALLOWED = [
    (S.CANDIDATE, S.AI_REJECTED),
    (S.CANDIDATE, S.PENDING_REVIEW),
    (S.PENDING_REVIEW, S.APPROVED),
    (S.PENDING_REVIEW, S.REJECTED),
    (S.APPROVED, S.ESCALATED),
]


def _verification(**over) -> dict:
    base = dict(
        is_incident=True,
        incident_type="snatch_theft",
        confidence=0.9,
        summary="Rider snatched a bag.",
        suspects=[PersonDesc(track_id=3, description="black helmet, red jacket")],
        victim=PersonDesc(track_id=1, description="woman, blue top"),
        vehicle=VehicleDesc(type="motorcycle", colour="black", plate_visible=False, plate_text=None),
        escape_direction="north",
    )
    base.update(over)
    return base


@pytest.mark.parametrize("current,new", ALLOWED)
def test_valid_transitions(current, new):
    assert transition(current, new) == new


def test_invalid_transitions_raise():
    bad = [
        (S.REJECTED, S.APPROVED),
        (S.PENDING_REVIEW, S.ESCALATED),
        (S.APPROVED, S.APPROVED),
        (S.AI_REJECTED, S.PENDING_REVIEW),
        (S.ESCALATED, S.APPROVED),
        (S.CANDIDATE, S.APPROVED),
    ]
    for current, new in bad:
        with pytest.raises(InvalidTransition):
            transition(current, new)


def test_verification_result_rejects_confidence_above_1():
    with pytest.raises(ValidationError):
        VerificationResult(**_verification(confidence=1.2))
    with pytest.raises(ValidationError):
        VerificationResult(**_verification(confidence=-0.1))


def test_incident_json_roundtrip():
    now = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    cand = CandidateEvent(
        camera_id="CAM-07", pts=12.5, loop=0, trigger="rule",
        suspect_track_ids=[3], victim_track_id=1, motorcycle_track_id=2, detected_at=now,
    )
    inc = Incident(
        id="INC-20261011-0001", camera_id="CAM-07", status=S.PENDING_REVIEW, candidate=cand,
        verification=VerificationResult(**_verification()), verification_error=None,
        escape_direction="north", escape_exit="Gate B", snapshot_files=["a.jpg"],
        clip_file="case-1.mp4", clip_start=8.5, clip_end=15.5,
        guard_decision_at=None, operator=None,
        escalation=[EscalationStep(channel="police_call", status="queued", detail=None, updated_at=now)],
        metrics={"candidate_s": 0.0}, created_at=now,
    )
    again = Incident.model_validate_json(inc.model_dump_json())
    assert again == inc
    assert again.status is S.PENDING_REVIEW
