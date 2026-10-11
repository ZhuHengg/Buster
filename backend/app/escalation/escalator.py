import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Protocol
from xml.sax.saxutils import escape as xml_escape

from app.config import CameraConfig, Settings
from app.escalation.script import build_call_script, build_sms
from app.models import EscalationStep, Incident, IncidentStatus

log = logging.getLogger(__name__)

# Twilio call status -> EscalationStep status
TWILIO_STATUS = {
    "queued": "queued",
    "initiated": "queued",
    "ringing": "ringing",
    "in-progress": "in_progress",
    "completed": "completed",
    "failed": "failed",
    "busy": "failed",
    "no-answer": "failed",
    "canceled": "failed",
}
TERMINAL = {"completed", "failed"}


class NotApproved(Exception):
    """Escalation was requested for an incident the guard has not approved."""


class Escalator(Protocol):
    async def escalate(self, incident: Incident, camera: CameraConfig) -> None: ...


def _require_approved(incident: Incident) -> None:
    if incident.status is not IncidentStatus.APPROVED:
        raise NotApproved(f"{incident.id} is {incident.status.value}, not APPROVED")


async def _mark(service: Any, incident: Incident, channel: str, status: str, detail: str | None = None) -> None:
    step = EscalationStep(channel=channel, status=status, detail=detail, updated_at=datetime.now(timezone.utc))
    await service.mark_escalation(incident.id, step)


class TwilioEscalator:
    def __init__(
        self,
        settings: Settings,
        service: Any,
        client: Any = None,
        poll_interval: float = 2.0,
        max_wait: float = 40.0,
    ):
        self.settings = settings
        self.service = service
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        if client is None:
            from twilio.rest import Client

            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.client = client

    async def escalate(self, incident: Incident, camera: CameraConfig) -> None:
        _require_approved(incident)
        operator = incident.operator or self.settings.operator_name
        await _mark(self.service, incident, "police_call", "queued")
        twiml = f'<Response><Say voice="alice">{xml_escape(build_call_script(incident, camera, operator))}</Say></Response>'
        sid: str | None = None
        try:
            call = await asyncio.to_thread(
                self.client.calls.create,
                to=self.settings.police_number,
                from_=self.settings.twilio_from_number,
                twiml=twiml,
            )
            sid = call.sid
        except Exception as exc:  # never lose the SMS because the call could not be placed
            log.exception("police call failed for %s", incident.id)
            await _mark(self.service, incident, "police_call", "failed", str(exc))
        await asyncio.gather(
            self._poll_call(incident, sid) if sid else asyncio.sleep(0),
            self._send_sms(incident, camera, "police_sms", self.settings.police_number, for_gate=False),
            self._send_sms(incident, camera, "gate_sms", self.settings.gate_number, for_gate=True),
        )

    async def _poll_call(self, incident: Incident, sid: str) -> None:
        last = "queued"
        deadline = time.monotonic() + self.max_wait
        while time.monotonic() < deadline:
            try:
                raw = (await asyncio.to_thread(lambda: self.client.calls(sid).fetch().status))
            except Exception:
                log.exception("call status poll failed for %s", sid)
                raw = None
            mapped = TWILIO_STATUS.get(raw) if raw else None
            if mapped and mapped != last:
                await _mark(self.service, incident, "police_call", mapped, raw if mapped == "failed" else None)
                last = mapped
            if last in TERMINAL:
                return
            await asyncio.sleep(self.poll_interval)

    async def _send_sms(
        self, incident: Incident, camera: CameraConfig, channel: str, number: str | None, for_gate: bool
    ) -> None:
        if not number:
            await _mark(self.service, incident, channel, "skipped", "no number configured")
            return
        try:
            await asyncio.to_thread(
                self.client.messages.create,
                to=number,
                from_=self.settings.twilio_from_number,
                body=build_sms(incident, camera, for_gate=for_gate),
            )
        except Exception as exc:
            log.exception("%s failed for %s", channel, incident.id)
            await _mark(self.service, incident, channel, "failed", str(exc))
            return
        await _mark(self.service, incident, channel, "sent", f"to {number}")


class DryRunEscalator:
    """No credentials: simulates the escalation so the demo runs end to end."""

    def __init__(self, service: Any, delays: tuple[float, float, float] = (0.5, 1.5, 4.0)):
        self.service = service
        self.delays = delays

    async def escalate(self, incident: Incident, camera: CameraConfig) -> None:
        _require_approved(incident)
        note = "Dry run: no real call placed"
        await _mark(self.service, incident, "police_call", "queued", note)
        await asyncio.sleep(self.delays[0])
        await _mark(self.service, incident, "police_call", "ringing", note)
        await _mark(self.service, incident, "police_sms", "sent", "Dry run: no real SMS sent")
        await _mark(self.service, incident, "gate_sms", "sent", "Dry run: no real SMS sent")
        await asyncio.sleep(self.delays[1])
        await _mark(self.service, incident, "police_call", "in_progress", note)
        await asyncio.sleep(self.delays[2])
        await _mark(self.service, incident, "police_call", "completed", note)


def make_escalator(settings: Settings, service: Any) -> Escalator:
    if all(
        (settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number, settings.police_number)
    ):
        return TwilioEscalator(settings, service)
    return DryRunEscalator(service)
