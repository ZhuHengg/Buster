import json
from pathlib import Path

import pytest

from app.config import CameraConfig, Settings, load_cameras


def _cam(id_: str, clip: str | None, analyse: bool) -> dict:
    return {
        "id": id_,
        "name": f"Camera {id_}",
        "location": "Elmina Shoplot Row B",
        "clip": clip,
        "analyse": analyse,
        "exits": {"up": "Gate B"},
        "compass": {"up": "north"},
    }


def _write(tmp_path: Path, cams: list[dict]) -> Path:
    path = tmp_path / "cameras.json"
    path.write_text(json.dumps(cams), encoding="utf-8")
    return path


def test_load_cameras_ok(tmp_path: Path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    path = _write(tmp_path, [_cam("CAM-01", "a.mp4", True), _cam("CAM-02", None, False)])
    cams = load_cameras(path)
    assert [c.id for c in cams] == ["CAM-01", "CAM-02"]
    assert isinstance(cams[0], CameraConfig)
    assert cams[0].exits == {"up": "Gate B"}
    assert cams[0].compass == {"up": "north"}
    assert cams[1].clip is None


def test_load_cameras_duplicate_id_raises(tmp_path: Path):
    path = _write(tmp_path, [_cam("CAM-01", None, False), _cam("CAM-01", None, False)])
    with pytest.raises(ValueError, match="duplicate"):
        load_cameras(path)


def test_load_cameras_missing_clip_raises_only_when_analysed(tmp_path: Path):
    ok = _write(tmp_path, [_cam("CAM-01", "missing.mp4", False)])
    assert load_cameras(ok)[0].clip == "missing.mp4"
    bad = _write(tmp_path, [_cam("CAM-01", "missing.mp4", True)])
    with pytest.raises(ValueError, match="missing"):
        load_cameras(bad)


def test_settings_defaults_without_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for var in ("CLAUDE_MODEL", "MODE", "ANTHROPIC_API_KEY", "TWILIO_ACCOUNT_SID"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.claude_model == "claude-opus-5-5"
    assert s.mode == "live"
    assert s.anthropic_api_key is None
    assert s.operator_name == "CMS Operator 1"
    assert s.db_path.name == "incidents.db"
