import pytest

from app.escalation.escalator import DryRunEscalator, NotApproved, TwilioEscalator, make_escalator
from app.models import IncidentStatus
from tests.escalation.conftest import FakeTwilio, full_settings, make_incident

FAST = dict(poll_interval=0.01, max_wait=1.0)


@pytest.mark.parametrize(
    "status",
    [IncidentStatus.PENDING_REVIEW, IncidentStatus.REJECTED, IncidentStatus.ESCALATED, IncidentStatus.CANDIDATE],
)
async def test_escalate_refuses_non_approved(spy, camera, status):
    inc = make_incident(status=status)
    twilio = FakeTwilio()
    for escalator in (
        TwilioEscalator(full_settings(), spy, client=twilio, **FAST),
        DryRunEscalator(spy, delays=(0, 0, 0)),
    ):
        with pytest.raises(NotApproved):
            await escalator.escalate(inc, camera)
    assert twilio.created_calls == [] and twilio.sent == []
    assert spy.steps == []


async def test_twilio_escalator_maps_statuses(spy, incident, camera):
    twilio = FakeTwilio(call_statuses=("queued", "ringing", "in-progress", "completed"))
    await TwilioEscalator(full_settings(), spy, client=twilio, **FAST).escalate(incident, camera)
    assert spy.statuses("police_call") == ["queued", "ringing", "in_progress", "completed"]
    call = twilio.created_calls[0]
    assert call["to"] == "+60123456789" and call["from_"] == "+15550001"
    assert call["twiml"].startswith("<Response><Say voice=\"alice\">") and "Jalan Limau Manis" in call["twiml"]
    assert spy.statuses("police_sms") == ["sent"] and spy.statuses("gate_sms") == ["sent"]
    assert {m["to"] for m in twilio.sent} == {"+60123456789", "+60129876543"}
    gate = next(m for m in twilio.sent if m["to"] == "+60129876543")
    assert gate["body"].startswith("INTERCEPT: ")


@pytest.mark.parametrize("final", ["failed", "busy", "no-answer"])
async def test_twilio_call_failure_statuses_map_to_failed(spy, incident, camera, final):
    twilio = FakeTwilio(call_statuses=("queued", "ringing", final))
    await TwilioEscalator(full_settings(), spy, client=twilio, **FAST).escalate(incident, camera)
    assert spy.statuses("police_call")[-1] == "failed"
    assert any(final == s.detail for s in spy.steps if s.channel == "police_call")


async def test_sms_failure_does_not_raise(spy, incident, camera):
    twilio = FakeTwilio(sms_error=RuntimeError("sms provider down"))
    await TwilioEscalator(full_settings(), spy, client=twilio, **FAST).escalate(incident, camera)
    assert spy.statuses("police_sms") == ["failed"] and spy.statuses("gate_sms") == ["failed"]
    assert spy.statuses("police_call")[-1] == "completed"  # call unaffected


async def test_call_creation_failure_does_not_raise_and_still_sends_sms(spy, incident, camera):
    twilio = FakeTwilio()

    def boom(**kw):
        raise RuntimeError("twilio 21215: geo permission")

    twilio.calls.create = boom
    await TwilioEscalator(full_settings(), spy, client=twilio, **FAST).escalate(incident, camera)
    assert spy.statuses("police_call") == ["queued", "failed"]
    failed = [s for s in spy.steps if s.channel == "police_call"][-1]
    assert "geo permission" in failed.detail
    assert spy.statuses("police_sms") == ["sent"]


async def test_missing_gate_number_skipped(spy, incident, camera):
    twilio = FakeTwilio()
    escalator = TwilioEscalator(full_settings(gate_number=None), spy, client=twilio, **FAST)
    await escalator.escalate(incident, camera)
    assert spy.statuses("gate_sms") == ["skipped"]
    assert [m["to"] for m in twilio.sent] == ["+60123456789"]


async def test_dry_run_emits_ringing_then_completed(spy, incident, camera):
    await DryRunEscalator(spy, delays=(0.0, 0.0, 0.0)).escalate(incident, camera)
    assert spy.statuses("police_call") == ["queued", "ringing", "in_progress", "completed"]
    assert spy.statuses("police_sms") == ["sent"] and spy.statuses("gate_sms") == ["sent"]
    assert all(s.detail and "dry run" in s.detail.lower() for s in spy.steps)


def test_make_escalator_selects_by_credentials(spy):
    assert isinstance(make_escalator(full_settings(), spy), TwilioEscalator)
    assert isinstance(make_escalator(full_settings(twilio_auth_token=None), spy), DryRunEscalator)
    assert isinstance(make_escalator(full_settings(police_number=None), spy), DryRunEscalator)
    assert isinstance(make_escalator(full_settings(twilio_account_sid=None), spy), DryRunEscalator)
    assert isinstance(make_escalator(full_settings(twilio_from_number=None), spy), DryRunEscalator)
