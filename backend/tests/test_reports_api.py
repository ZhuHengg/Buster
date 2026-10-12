import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.reports import load_reports


@pytest.fixture
def reports_dir(tmp_path: Path) -> Path:
    d = tmp_path / "reports"
    d.mkdir()
    return d


@pytest.fixture
def client(tmp_path: Path, reports_dir: Path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "cameras.json").write_text("[]", encoding="utf-8")
    settings = Settings(_env_file=None, data_dir=data, db_path=data / "i.db", reports_dir=reports_dir)
    with TestClient(create_app(settings, start_pipelines=False)) as c:
        yield c


def test_reports_missing_files_returns_nulls(client):
    res = client.get("/api/reports")
    assert res.status_code == 200
    body = res.json()
    assert body["benchmark"] is None and body["scale"] is None and body["baseline"] is None
    assert "scripts/benchmark.py" in body["generated_hint"] and "scripts/scale_test.py" in body["generated_hint"]


def test_reports_returns_files_when_present(client, reports_dir):
    bench = {"meta": {"verifier": "claude"}, "test": None, "demo": None}
    scale = {"meta": {}, "target_fps": 10.0, "rows": [], "max_cameras_ok": 6}
    base = {"time_to_notice_s": 90, "source": "guard interviews, n=5"}
    (reports_dir / "benchmark.json").write_text(json.dumps(bench), encoding="utf-8")
    (reports_dir / "scale.json").write_text(json.dumps(scale), encoding="utf-8")
    (reports_dir / "baseline.json").write_text(json.dumps(base), encoding="utf-8")
    body = client.get("/api/reports").json()
    assert body["benchmark"] == bench and body["scale"] == scale
    assert body["baseline"] == {"time_to_notice_s": 90, "source": "guard interviews, n=5"}


def test_feedback_rows_count_comes_from_labels(tmp_path, reports_dir):
    labels = tmp_path / "labels.csv"
    labels.write_text("source_id,origin\nfb_INC-1,feedback\nstaged_1,staged\nfb_INC-2,feedback\n", encoding="utf-8")
    assert load_reports(reports_dir, labels_path=labels)["feedback_rows"] == 2
    assert load_reports(reports_dir, labels_path=tmp_path / "none.csv")["feedback_rows"] == 0


def test_corrupt_or_wrong_shaped_files_are_treated_as_missing(reports_dir):
    (reports_dir / "benchmark.json").write_text("{not json", encoding="utf-8")
    (reports_dir / "scale.json").write_text("[1, 2]", encoding="utf-8")
    out = load_reports(reports_dir)
    assert out["benchmark"] is None and out["scale"] is None


def test_baseline_never_invents_a_number(reports_dir):
    (reports_dir / "baseline.json").write_text(
        json.dumps({"time_to_notice_s": "about a minute", "source": "x"}), encoding="utf-8")
    assert load_reports(reports_dir)["baseline"]["time_to_notice_s"] is None
    (reports_dir / "baseline.json").write_text(json.dumps({"time_to_notice_s": None}), encoding="utf-8")
    assert load_reports(reports_dir)["baseline"]["time_to_notice_s"] is None
    (reports_dir / "baseline.json").write_text(json.dumps({"time_to_notice_s": True}), encoding="utf-8")
    assert load_reports(reports_dir)["baseline"]["time_to_notice_s"] is None  # a bool is not a number
