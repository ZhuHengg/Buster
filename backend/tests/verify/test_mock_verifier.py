import json

from app.verify.claude_verifier import ClaudeVerifier
from app.verify.mock_verifier import MockVerifier, make_verifier
from tests.verify.conftest import VALID_JSON


async def test_mock_verifier_uses_fixture_when_present(tmp_path, camera, candidate):
    fixture = json.loads(VALID_JSON)
    fixture["summary"] = "From the fixture file."
    (tmp_path / "CAM-02.json").write_text(json.dumps(fixture), encoding="utf-8")
    result = await MockVerifier(tmp_path).verify(candidate, [], camera)
    assert result.summary == "From the fixture file."
    assert result.confidence == 0.93


async def test_mock_verifier_default_is_snatch_theft(tmp_path, camera, candidate):
    result = await MockVerifier(tmp_path).verify(candidate, [], camera)
    assert result.is_incident is True
    assert result.incident_type == "snatch_theft"
    assert result.confidence == 0.9
    assert result.suspects[0].track_id == 16
    assert result.victim is not None and result.victim.track_id == 1


def test_make_verifier_without_key_returns_mock(tmp_path):
    from app.config import Settings

    s = Settings(_env_file=None, anthropic_api_key=None, gemini_api_key=None, data_dir=tmp_path)
    assert isinstance(make_verifier(s), MockVerifier)


def test_make_verifier_with_key_returns_claude(tmp_path):
    from app.config import Settings

    s = Settings(_env_file=None, anthropic_api_key="k", gemini_api_key=None, data_dir=tmp_path)
    assert isinstance(make_verifier(s), ClaudeVerifier)


def test_make_verifier_prefers_gemini(tmp_path):
    from app.config import Settings
    from app.verify.gemini_verifier import GeminiVerifier

    s = Settings(_env_file=None, anthropic_api_key="k", gemini_api_key="g", data_dir=tmp_path)
    assert isinstance(make_verifier(s), GeminiVerifier)
