import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import CameraConfig
from app.incidents.service import IncidentService
from app.incidents.store import IncidentStore
from app.models import (
    CandidateEvent,
    EscalationStep,
    IncidentStatus,
    InvalidTransition,
    PersonDesc,
    VerificationResult,
)

S = IncidentStatus


def _candidate(pts: float = 12.0, camera_id: str = "CAM-02") -> CandidateEvent:
    return CandidateEvent(
        camera_id=camera_id, pts=pts, loop=0, trigger="rule", suspect_track_ids=[16, 17],
        victim_track_id=1, motorcycle_track_id=18,
        detected_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )


def _verification(is_incident: bool = True) -> VerificationResult:
    return VerificationResult(
        is_incident=is_incident, incident_type="snatch_theft" if is_incident else "none",
        confidence=0.9, summary="x", suspects=[PersonDesc(track_id=16, description="rider")],
        escape_direction="east" if is_incident else "unknown",
    )


def _step(status: str, channel: str = "police_call") -> EscalationStep:
    return EscalationStep(channel=channel, status=status, updated_at=datetime.now(timezone.utc))


@pytest.fixture
def camera() -> CameraConfig:
    return CameraConfig(id="CAM-02", name="Row B", location="Jalan Limau Manis", clip="case-2.mp4", analyse=True)


@pytest.fixture
def changes() -> list:
    return []


@pytest.fixture
def service(tmp_path: Path, changes: list) -> IncidentService:
    async def on_change(incident):
        changes.append((incident.id, incident.status))

    snaps = tmp_path / "snaps"
    snaps.mkdir()
    return IncidentService(IncidentStore(tmp_path / "incidents.db"), snaps, on_change)


async def _open(service, camera, pts: float = 12.0):
    return await service.open(_candidate(pts), camera, "case-2.mp4", {16: b"jpeg16", 17: b"jpeg17"})


async def _pending(service, camera):
    inc = await _open(service, camera)
    return await service.attach_verification(inc.id, _verification(), None, ("east", "Gate B"))


async def test_open_writes_snapshots_and_sets_clip_window(service, camera, tmp_path):
    inc = await _open(service, camera)
    assert re.fullmatch(r"INC-\d{8}-0001", inc.id)
    assert inc.status is S.CANDIDATE
    assert (inc.clip_start, inc.clip_end, inc.clip_file) == (8.0, 15.0, "case-2.mp4")
    assert sorted(inc.snapshot_files) == [f"{inc.id}_16.jpg", f"{inc.id}_17.jpg"]
    for name in inc.snapshot_files:
        assert (tmp_path / "snaps" / name).exists()
    assert inc.metrics["candidate_s"] >= 0
    second = await _open(service, camera)
    assert second.id.endswith("-0002")


async def test_open_clamps_clip_start_at_zero(service, camera):
    inc = await _open(service, camera, pts=2.0)
    assert inc.clip_start == 0.0 and inc.clip_end == 5.0


async def test_verification_false_sets_ai_rejected_and_deletes_snapshots(service, camera, tmp_path):
    inc = await _open(service, camera)
    out = await service.attach_verification(inc.id, _verification(False), None, (None, None))
    assert out.status is S.AI_REJECTED
    assert out.snapshot_files == []
    assert list((tmp_path / "snaps").iterdir()) == []


async def test_verification_true_goes_pending_with_direction(service, camera):
    out = await _pending(service, camera)
    assert out.status is S.PENDING_REVIEW
    assert (out.escape_direction, out.escape_exit) == ("east", "Gate B")
    assert out.metrics["verified_s"] >= out.metrics["candidate_s"]
    assert out.verification_error is None


async def test_verification_none_still_pending_review(service, camera):
    inc = await _open(service, camera)
    out = await service.attach_verification(inc.id, None, "AI verification unavailable: timed out", (None, None))
    assert out.status is S.PENDING_REVIEW
    assert out.verification is None
    assert "unavailable" in out.verification_error
    assert len(out.snapshot_files) == 2


async def test_approve_sets_operator_and_time(service, camera):
    inc = await _pending(service, camera)
    out = await service.approve(inc.id, "Aina")
    assert out.status is S.APPROVED
    assert out.operator == "Aina" and out.guard_decision_at is not None


async def test_approve_twice_raises(service, camera):
    inc = await _pending(service, camera)
    await service.approve(inc.id, "Aina")
    with pytest.raises(InvalidTransition):
        await service.approve(inc.id, "Aina")


async def test_approve_after_reject_raises(service, camera):
    inc = await _pending(service, camera)
    await service.reject(inc.id, "Aina")
    with pytest.raises(InvalidTransition):
        await service.approve(inc.id, "Aina")


async def test_reject_deletes_snapshots(service, camera, tmp_path):
    inc = await _pending(service, camera)
    out = await service.reject(inc.id, "Aina")
    assert out.status is S.REJECTED
    assert out.snapshot_files == []
    assert list((tmp_path / "snaps").iterdir()) == []


async def test_approve_unknown_incident_raises_keyerror(service):
    with pytest.raises(KeyError):
        await service.approve("INC-00000000-0000", "Aina")


async def test_mark_escalation_ringing_sets_escalated_and_metric(service, camera):
    inc = await _pending(service, camera)
    await service.approve(inc.id, "Aina")
    queued = await service.mark_escalation(inc.id, _step("queued"))
    assert queued.status is S.APPROVED and "call_placed_s" not in queued.metrics
    ringing = await service.mark_escalation(inc.id, _step("ringing"))
    assert ringing.status is S.ESCALATED
    assert ringing.metrics["call_placed_s"] > 0
    assert [s.status for s in ringing.escalation] == ["ringing"]  # upsert by channel
    done = await service.mark_escalation(inc.id, _step("completed"))
    assert done.status is S.ESCALATED
    assert done.metrics["call_placed_s"] == ringing.metrics["call_placed_s"]


async def test_mark_escalation_sms_does_not_escalate_or_set_metric(service, camera):
    inc = await _pending(service, camera)
    await service.approve(inc.id, "Aina")
    out = await service.mark_escalation(inc.id, _step("sent", "police_sms"))
    assert out.status is S.APPROVED and "call_placed_s" not in out.metrics


async def test_mark_escalation_requires_approval(service, camera):
    inc = await _pending(service, camera)
    with pytest.raises(InvalidTransition):
        await service.mark_escalation(inc.id, _step("ringing"))


async def test_on_change_called_for_each_transition(service, camera, changes):
    inc = await _pending(service, camera)  # open + attach
    await service.approve(inc.id, "Aina")
    await service.mark_escalation(inc.id, _step("ringing"))
    assert [s for _, s in changes] == [S.CANDIDATE, S.PENDING_REVIEW, S.APPROVED, S.ESCALATED]


async def test_store_roundtrip_and_list_order(service, camera):
    first = await _pending(service, camera)
    second = await _open(service, camera)
    assert service.store.get(first.id) == first
    assert service.store.get("nope") is None
    assert [i.id for i in service.store.list()] == [second.id, first.id]
    assert [i.id for i in service.store.list(S.PENDING_REVIEW)] == [first.id]
    assert [i.id for i in service.store.list(S.CANDIDATE)] == [second.id]
