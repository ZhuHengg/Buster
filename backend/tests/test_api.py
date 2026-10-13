import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import (
    CandidateEvent,
    Incident,
    IncidentStatus,
    PersonDesc,
    VerificationResult,
)

S = IncidentStatus


class FakeEscalator:
    def __init__(self):
        self.calls: list[tuple[str, IncidentStatus]] = []

    async def escalate(self, incident, camera):
        self.calls.append((incident.id, incident.status))


def _camera(id_: str, clip: str | None, analyse: bool) -> dict:
    return {
        "id": id_, "name": f"Cam {id_}", "location": "Jalan Limau Manis", "clip": clip, "analyse": analyse,
        "exits": {"up": "Gate B"}, "compass": {"up": "north"},
    }


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    writer = cv2.VideoWriter(str(d / "tiny.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 48))
    for i in range(20):
        writer.write(np.full((48, 64, 3), i * 10, dtype=np.uint8))
    writer.release()
    cams = [_camera("CAM-02", "tiny.mp4", True), _camera("CAM-03", None, False)]
    (d / "cameras.json").write_text(json.dumps(cams), encoding="utf-8")
    return d


@pytest.fixture
def escalator() -> FakeEscalator:
    return FakeEscalator()


@pytest.fixture
def client(data_dir: Path, escalator: FakeEscalator):
    settings = Settings(_env_file=None, data_dir=data_dir, db_path=data_dir / "incidents.db")
    app = create_app(settings, escalator=escalator, start_pipelines=False)
    with TestClient(app) as c:
        yield c


def seed(client: TestClient, id_: str = "INC-20261011-0001", status: S = S.PENDING_REVIEW, snapshots=()) -> Incident:
    now = datetime.now(timezone.utc)
    inc = Incident(
        id=id_, camera_id="CAM-02", status=status,
        candidate=CandidateEvent(
            camera_id="CAM-02", pts=5.0, loop=0, trigger="rule", suspect_track_ids=[3], victim_track_id=1,
            motorcycle_track_id=2, detected_at=now,
        ),
        verification=VerificationResult(
            is_incident=True, incident_type="snatch_theft", confidence=0.9, summary="x",
            suspects=[PersonDesc(track_id=3, description="rider")], escape_direction="north",
        ),
        escape_direction="north", escape_exit="Gate B", snapshot_files=list(snapshots),
        clip_file="tiny.mp4", clip_start=1.0, clip_end=8.0, created_at=now,
    )
    client.app.state.service.store.save(inc)
    return inc


def test_api_approve_runs_escalation_once(client, escalator):
    seed(client)
    first = client.post("/api/incidents/INC-20261011-0001/approve", json={"operator": "Aina"})
    assert first.status_code == 200
    assert first.json()["status"] == "APPROVED" and first.json()["operator"] == "Aina"
    second = client.post("/api/incidents/INC-20261011-0001/approve", json={"operator": "Aina"})
    assert second.status_code == 409
    assert escalator.calls == [("INC-20261011-0001", S.APPROVED)]


def test_api_approve_after_reject_is_409_and_never_escalates(client, escalator):
    seed(client)
    assert client.post("/api/incidents/INC-20261011-0001/reject", json={}).status_code == 200
    assert client.post("/api/incidents/INC-20261011-0001/approve", json={}).status_code == 409
    assert escalator.calls == []
    assert client.get("/api/incidents/INC-20261011-0001").json()["status"] == "REJECTED"


def test_api_default_operator_from_settings(client):
    seed(client)
    out = client.post("/api/incidents/INC-20261011-0001/reject")
    assert out.status_code == 200 and out.json()["operator"] == "CMS Operator 1"


def test_api_unknown_incident_is_404(client):
    assert client.get("/api/incidents/nope").status_code == 404
    assert client.post("/api/incidents/nope/approve", json={}).status_code == 404


def test_api_list_incidents_filters_by_status(client):
    seed(client, "INC-20261011-0001", S.PENDING_REVIEW)
    seed(client, "INC-20261011-0002", S.AI_REJECTED)
    assert {i["id"] for i in client.get("/api/incidents").json()} == {"INC-20261011-0001", "INC-20261011-0002"}
    only = client.get("/api/incidents", params={"status": "AI_REJECTED"}).json()
    assert [i["id"] for i in only] == ["INC-20261011-0002"]
    assert client.get("/api/incidents", params={"status": "BOGUS"}).status_code == 422


def test_api_cameras_include_sync_info(client):
    cams = {c["id"]: c for c in client.get("/api/cameras").json()}
    assert cams["CAM-02"]["clip"] == "tiny.mp4"
    assert cams["CAM-02"]["sync"]["duration"] == pytest.approx(2.0)
    assert cams["CAM-02"]["sync"]["fps"] == pytest.approx(10.0)
    assert cams["CAM-03"]["clip"] is None and cams["CAM-03"]["sync"] is None


def test_api_clip_supports_range(client, data_dir):
    resp = client.get("/media/clips/tiny.mp4", headers={"Range": "bytes=0-99"})
    assert resp.status_code == 206
    assert resp.headers["content-range"].startswith("bytes 0-99/")
    assert len(resp.content) == 100
    assert client.get("/media/clips/tiny.mp4").headers.get("accept-ranges") == "bytes"


def test_api_clip_rejects_traversal_and_unknown(client):
    assert client.get("/media/clips/missing.mp4").status_code == 404
    assert client.get("/media/clips/..%2Fincidents.db").status_code == 404
    assert client.get("/media/clips/cameras.json").status_code == 404  # only .mp4 is served


def test_api_snapshots_served(client, data_dir):
    snaps = data_dir / "snapshots"
    snaps.mkdir(exist_ok=True)
    (snaps / "INC-1_3.jpg").write_bytes(b"\xff\xd8jpeg")
    resp = client.get("/media/snapshots/INC-1_3.jpg")
    assert resp.status_code == 200 and resp.content == b"\xff\xd8jpeg"
    assert client.get("/media/snapshots/none.jpg").status_code == 404


def test_api_cors_allows_frontend_origin(client):
    resp = client.get("/api/cameras", headers={"Origin": "http://localhost:3000"})
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_ws_receives_broadcast(client):
    with client.websocket_connect("/ws") as ws:
        client.portal.call(client.app.state.hub.broadcast, {"type": "camera.sync", "camera_id": "CAM-02"})
        assert ws.receive_json() == {"type": "camera.sync", "camera_id": "CAM-02"}


def test_ws_receives_incident_updates_from_service(client):
    inc = seed(client)
    with client.websocket_connect("/ws") as ws:
        client.post(f"/api/incidents/{inc.id}/reject", json={"operator": "Aina"})
        msg = ws.receive_json()
    assert msg["type"] == "incident.updated"
    assert msg["incident"]["id"] == inc.id and msg["incident"]["status"] == "REJECTED"


def test_playback_api_gets_sets_and_restarts_and_broadcasts(client):
    assert client.get("/api/playback").json() == {"loop": True, "held": False}
    with client.websocket_connect("/ws") as ws:
        assert client.post("/api/playback", json={"loop": False}).json() == {"loop": False, "held": False}
        assert ws.receive_json() == {"type": "playback", "loop": False, "held": False}
        gen = client.app.state.playback.generation
        assert client.post("/api/playback/restart").status_code == 200
        assert client.app.state.playback.generation == gen + 1
    assert client.get("/api/playback").json()["loop"] is False


def test_api_delete_incident_removes_it_and_its_snapshots_and_broadcasts(client, data_dir):
    snaps = data_dir / "snapshots"
    snaps.mkdir(exist_ok=True)
    (snaps / "INC-1_3.jpg").write_bytes(b"jpg")
    seed(client, "INC-20261011-0001", snapshots=["INC-1_3.jpg"])
    seed(client, "INC-20261011-0002")
    with client.websocket_connect("/ws") as ws:
        res = client.delete("/api/incidents/INC-20261011-0001")
        assert res.status_code == 200 and res.json() == {"id": "INC-20261011-0001"}
        assert ws.receive_json() == {"type": "incident.deleted", "id": "INC-20261011-0001"}
    assert client.get("/api/incidents/INC-20261011-0001").status_code == 404
    assert [i["id"] for i in client.get("/api/incidents").json()] == ["INC-20261011-0002"]  # others untouched
    assert not (snaps / "INC-1_3.jpg").exists()


def test_api_delete_unknown_incident_is_404(client):
    assert client.delete("/api/incidents/nope").status_code == 404


def test_api_delete_a_pending_incident_clears_it_from_the_queue(client):
    seed(client, "INC-20261011-0001", S.PENDING_REVIEW)
    assert client.delete("/api/incidents/INC-20261011-0001").status_code == 200
    assert client.get("/api/incidents", params={"status": "PENDING_REVIEW"}).json() == []
