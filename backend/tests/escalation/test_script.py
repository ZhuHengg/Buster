from app.escalation.script import build_call_script, build_sms
from tests.escalation.conftest import make_incident


def test_call_script_contains_location_description_exit_operator(incident, camera):
    text = build_call_script(incident, camera, "Aina")
    assert "This is an automated alert from Sime Darby Property Central Monitoring" in text
    assert "snatch theft" in text
    assert "Jalan Limau Manis" in text
    assert "12:05" in text
    assert "black motorcycle" in text  # from the verification summary
    assert "dark helmet" in text
    assert "east" in text and "Gate B" in text
    assert "verified by Aina" in text
    first = text.split("I repeat")[0]
    assert text.count("Jalan Limau Manis") == 2 and first != text  # repeated once


def test_call_script_unverified_wording(camera):
    text = build_call_script(make_incident(verified=False), camera, "Aina")
    assert "unverified by AI, confirmed by operator" in text
    assert "Aina" in text
    assert "Jalan Limau Manis" in text


def test_gate_sms_starts_with_intercept_and_fits_320(incident, camera):
    sms = build_sms(incident, camera, for_gate=True)
    assert sms.startswith("INTERCEPT: ")
    assert "Gate B" in sms and "black" in sms
    assert len(sms) <= 320


def test_police_sms_has_reference_and_fits_320(incident, camera):
    sms = build_sms(incident, camera, for_gate=False)
    assert "INC-20261011-0001" in sms and "Jalan Limau Manis" in sms
    assert not sms.startswith("INTERCEPT")
    assert len(sms) <= 320


def test_sms_truncated_to_320(incident, camera):
    incident.verification.summary = "x" * 900
    incident.verification.suspects[0].description = "y" * 900
    for gate in (True, False):
        assert len(build_sms(incident, camera, for_gate=gate)) <= 320


def test_sms_without_verification_still_useful(camera):
    sms = build_sms(make_incident(verified=False), camera, for_gate=True)
    assert sms.startswith("INTERCEPT: ") and "Gate B" in sms
