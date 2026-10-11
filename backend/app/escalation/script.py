from datetime import timedelta, timezone

from app.config import CameraConfig
from app.models import Incident

MALAYSIA = timezone(timedelta(hours=8))
SMS_LIMIT = 320
INTRO = "This is an automated alert from Sime Darby Property Central Monitoring."


def _clock(incident: Incident) -> str:
    return incident.candidate.detected_at.astimezone(MALAYSIA).strftime("%H:%M")


def _incident_type(incident: Incident) -> str:
    if incident.verification is None:
        return "suspected snatch theft"
    return incident.verification.incident_type.replace("_", " ")


def _suspects(incident: Incident) -> str:
    v = incident.verification
    return "; ".join(s.description for s in v.suspects) if v and v.suspects else ""


def _vehicle(incident: Incident) -> str:
    v = incident.verification.vehicle if incident.verification else None
    if v is None:
        return ""
    text = f"{v.colour} {v.type}".strip()
    if v.plate_visible and v.plate_text:
        text += f", plate {v.plate_text}"
    return text


def _escape(incident: Incident) -> str:
    parts = []
    if incident.escape_direction:
        parts.append(f"escaping {incident.escape_direction}")
    if incident.escape_exit:
        parts.append(f"towards {incident.escape_exit}")
    return " ".join(parts)


def _clip(text: str) -> str:
    return text if len(text) <= SMS_LIMIT else text[: SMS_LIMIT - 3].rstrip() + "..."


def build_call_script(incident: Incident, camera: CameraConfig, operator: str) -> str:
    lines = [
        INTRO,
        f"A {_incident_type(incident)} was detected at {camera.location}, camera {camera.name}, at {_clock(incident)}.",
    ]
    if incident.verification:
        lines.append(incident.verification.summary)
        if _suspects(incident):
            lines.append(f"Suspect: {_suspects(incident)}.")
        if _vehicle(incident):
            lines.append(f"Vehicle: {_vehicle(incident)}.")
    if _escape(incident):
        lines.append(f"The vehicle is {_escape(incident)}.")
    if incident.verification:
        lines.append(f"This incident was verified by {operator}.")
    else:
        lines.append(f"Incident unverified by AI, confirmed by operator {operator}.")
    body = " ".join(lines)
    return f"{body} I repeat. {body}"


def build_sms(incident: Incident, camera: CameraConfig, for_gate: bool) -> str:
    when = f"{camera.location} {_clock(incident)}"
    if for_gate:
        what = " ".join(p for p in (_vehicle(incident), _suspects(incident)) if p) or "suspect vehicle"
        dest = f" heading to {incident.escape_exit}" if incident.escape_exit else ""
        return _clip(f"INTERCEPT: {what}{dest}. {when}. Ref {incident.id}.")
    parts = [f"ALERT {incident.id}: {_incident_type(incident)} at {when} ({camera.name})."]
    if incident.verification:
        parts.append(incident.verification.summary)
    if _suspects(incident):
        parts.append(f"Suspect: {_suspects(incident)}.")
    if _vehicle(incident):
        parts.append(f"Vehicle: {_vehicle(incident)}.")
    if _escape(incident):
        parts.append(f"{_escape(incident).capitalize()}.")
    if incident.operator:
        parts.append(f"Confirmed by {incident.operator}.")
    return _clip(" ".join(parts))
