from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Track(BaseModel):
    id: int
    cls: Literal["person", "motorcycle"]
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 in source pixels
    conf: float
    keypoints: list[tuple[float, float, float]] | None = None  # COCO-17 x, y, conf; persons only


class FrameDetections(BaseModel):
    camera_id: str
    pts: float  # seconds since clip start
    frame_w: int
    frame_h: int
    tracks: list[Track]
    loop: int = 0  # increments each time the clip wraps


class CandidateEvent(BaseModel):
    camera_id: str
    pts: float
    loop: int
    trigger: Literal["rule", "model"]
    suspect_track_ids: list[int]
    victim_track_id: int | None = None
    motorcycle_track_id: int | None = None
    detected_at: datetime


class PersonDesc(BaseModel):
    track_id: int | None = None
    description: str


class VehicleDesc(BaseModel):
    type: str
    colour: str
    plate_visible: bool
    plate_text: str | None = None


class VerificationResult(BaseModel):
    is_incident: bool
    incident_type: Literal["snatch_theft", "robbery", "assault", "other", "none"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    suspects: list[PersonDesc]
    victim: PersonDesc | None = None
    vehicle: VehicleDesc | None = None
    escape_direction: Literal["north", "south", "east", "west", "unknown"]


class IncidentStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    AI_REJECTED = "AI_REJECTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


class EscalationStep(BaseModel):
    channel: Literal["police_call", "police_sms", "gate_sms"]
    status: Literal["queued", "ringing", "in_progress", "completed", "sent", "failed", "skipped"]
    detail: str | None = None
    updated_at: datetime


class Incident(BaseModel):
    id: str
    camera_id: str
    status: IncidentStatus
    candidate: CandidateEvent
    verification: VerificationResult | None = None
    verification_error: str | None = None
    escape_direction: str | None = None  # compass word
    escape_exit: str | None = None
    snapshot_files: list[str] = []
    clip_file: str
    clip_start: float
    clip_end: float
    guard_decision_at: datetime | None = None
    operator: str | None = None
    escalation: list[EscalationStep] = []
    metrics: dict[str, float] = {}  # candidate_s, verified_s, shown_s, call_placed_s
    created_at: datetime


class InvalidTransition(Exception):
    pass


_ALLOWED: set[tuple[IncidentStatus, IncidentStatus]] = {
    (IncidentStatus.CANDIDATE, IncidentStatus.AI_REJECTED),
    (IncidentStatus.CANDIDATE, IncidentStatus.PENDING_REVIEW),
    (IncidentStatus.PENDING_REVIEW, IncidentStatus.APPROVED),
    (IncidentStatus.PENDING_REVIEW, IncidentStatus.REJECTED),
    (IncidentStatus.APPROVED, IncidentStatus.ESCALATED),
}


def transition(current: IncidentStatus, new: IncidentStatus) -> IncidentStatus:
    if (current, new) not in _ALLOWED:
        raise InvalidTransition(f"{current.value} -> {new.value}")
    return new
