from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path

from app.config import CameraConfig
from app.incidents.store import IncidentStore
from app.models import (
    CandidateEvent,
    EscalationStep,
    Incident,
    IncidentStatus,
    InvalidTransition,
    VerificationResult,
    transition,
)

S = IncidentStatus
CALL_PLACED = {"ringing", "in_progress", "completed"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IncidentService:
    """Incident lifecycle. Every mutation is read-modify-write with no await in between, so
    concurrent guard actions on one incident cannot both succeed (one gets InvalidTransition)."""

    def __init__(
        self,
        store: IncidentStore,
        snapshots_dir: Path,
        on_change: Callable[[Incident], Awaitable[None]],
    ):
        self.store = store
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.on_change = on_change

    # -- helpers -------------------------------------------------------------------------
    def _require(self, incident_id: str) -> Incident:
        incident = self.store.get(incident_id)
        if incident is None:
            raise KeyError(incident_id)
        return incident

    def _elapsed(self, incident: Incident) -> float:
        return (_now() - incident.candidate.detected_at).total_seconds()

    def _delete_snapshots(self, incident: Incident) -> None:
        for name in incident.snapshot_files:
            (self.snapshots_dir / name).unlink(missing_ok=True)
        incident.snapshot_files = []

    async def _commit(self, incident: Incident) -> Incident:
        self.store.save(incident)
        await self.on_change(incident)
        return incident

    def _next_id(self) -> str:
        prefix = f"INC-{_now():%Y%m%d}-"
        return f"{prefix}{self.store.count_with_prefix(prefix) + 1:04d}"

    # -- lifecycle -----------------------------------------------------------------------
    async def open(
        self, candidate: CandidateEvent, camera: CameraConfig, clip_file: str, snapshots: dict[int, bytes]
    ) -> Incident:
        incident_id = self._next_id()
        files: list[str] = []
        for track_id, data in snapshots.items():
            name = f"{incident_id}_{track_id}.jpg"
            (self.snapshots_dir / name).write_bytes(data)
            files.append(name)
        incident = Incident(
            id=incident_id,
            camera_id=camera.id,
            status=S.CANDIDATE,
            candidate=candidate,
            snapshot_files=files,
            clip_file=clip_file,
            clip_start=max(0.0, candidate.pts - 4.0),
            clip_end=candidate.pts + 3.0,
            created_at=_now(),
        )
        incident.metrics["candidate_s"] = round(self._elapsed(incident), 3)
        return await self._commit(incident)

    async def attach_verification(
        self,
        incident_id: str,
        result: VerificationResult | None,
        error: str | None,
        direction: tuple[str | None, str | None],
    ) -> Incident:
        incident = self._require(incident_id)
        rejected = result is not None and not result.is_incident
        incident.status = transition(incident.status, S.AI_REJECTED if rejected else S.PENDING_REVIEW)
        incident.verification = result
        incident.verification_error = None
        compass, exit_name = direction
        if result is None:
            incident.verification_error = error or "AI verification unavailable"
        elif compass is None and result.escape_direction != "unknown":
            compass = result.escape_direction
        incident.escape_direction, incident.escape_exit = compass, exit_name
        incident.metrics["verified_s"] = round(self._elapsed(incident), 3)
        if rejected:
            self._delete_snapshots(incident)
        else:
            incident.metrics["shown_s"] = incident.metrics["verified_s"]  # card is pushed to the CMS now
        return await self._commit(incident)

    async def _decide(self, incident_id: str, operator: str, new: IncidentStatus) -> Incident:
        incident = self._require(incident_id)
        incident.status = transition(incident.status, new)
        incident.operator = operator
        incident.guard_decision_at = _now()
        if new is S.REJECTED:
            self._delete_snapshots(incident)
        return await self._commit(incident)

    async def approve(self, incident_id: str, operator: str) -> Incident:
        return await self._decide(incident_id, operator, S.APPROVED)

    async def reject(self, incident_id: str, operator: str) -> Incident:
        return await self._decide(incident_id, operator, S.REJECTED)

    async def mark_escalation(self, incident_id: str, step: EscalationStep) -> Incident:
        incident = self._require(incident_id)
        if incident.status not in (S.APPROVED, S.ESCALATED):
            raise InvalidTransition(f"cannot escalate an incident in status {incident.status.value}")
        incident.escalation = [s for s in incident.escalation if s.channel != step.channel] + [step]
        if step.channel == "police_call" and step.status in CALL_PLACED:
            incident.metrics.setdefault("call_placed_s", round(self._elapsed(incident), 3))
            if incident.status is S.APPROVED:
                incident.status = transition(incident.status, S.ESCALATED)
        return await self._commit(incident)
