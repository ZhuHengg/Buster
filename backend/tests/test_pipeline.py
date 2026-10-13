import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from app.config import CameraConfig, Settings
from app.incidents.service import IncidentService
from app.incidents.store import IncidentStore
from app.models import (
    CandidateEvent,
    FrameDetections,
    IncidentStatus,
    PersonDesc,
    Track,
    VerificationResult,
)
from app.pipeline import CameraPipeline, ReplayPipeline
from app.verify.base import VerificationUnavailable
from app.verify.mock_verifier import MockVerifier
from app.video.buffer import FrameBuffer

S = IncidentStatus


class FakeHub:
    def __init__(self):
        self.messages: list[dict] = []

    async def broadcast(self, msg: dict) -> None:
        self.messages.append(msg)

    def of_type(self, type_: str) -> list[dict]:
        return [m for m in self.messages if m["type"] == type_]


class FakeDetector:
    """Person 1 (victim), motorcycle 2 and rider 3, all static, inside a 200x200 frame."""

    def __init__(self):
        self.resets = 0
        self.calls = 0

    def process(self, frame, camera_id, pts, loop) -> FrameDetections:
        self.calls += 1
        tracks = [
            Track(id=1, cls="person", bbox=(20.0, 20.0, 70.0, 180.0), conf=0.9),
            Track(id=2, cls="motorcycle", bbox=(100.0, 100.0, 190.0, 190.0), conf=0.9),
            Track(id=3, cls="person", bbox=(120.0, 40.0, 170.0, 150.0), conf=0.9),
        ]
        return FrameDetections(camera_id=camera_id, pts=pts, frame_w=200, frame_h=200, tracks=tracks, loop=loop)

    def reset(self) -> None:
        self.resets += 1


class FakeTrigger:
    def __init__(self, fire_on_call: int | None = 10):
        self.fire_on_call, self.calls, self.resets = fire_on_call, 0, 0

    def update(self, fd: FrameDetections) -> CandidateEvent | None:
        self.calls += 1
        if self.calls == self.fire_on_call:
            return CandidateEvent(
                camera_id=fd.camera_id, pts=fd.pts, loop=fd.loop, trigger="rule", suspect_track_ids=[3],
                victim_track_id=1, motorcycle_track_id=2, detected_at=datetime.now(timezone.utc),
            )
        return None

    def reset(self) -> None:
        self.resets += 1
        self.calls = 0


class RaisingVerifier:
    def __init__(self, exc: Exception):
        self.exc = exc

    async def verify(self, candidate, keyframes, camera):
        raise self.exc


def make_source(n: int, fps: int = 10, loops: tuple[int, ...] = (0,)):
    frame = np.full((200, 200, 3), 100, dtype=np.uint8)
    for loop in loops:
        for i in range(n):
            yield frame.copy(), i / fps, loop


@pytest.fixture
def camera() -> CameraConfig:
    return CameraConfig(
        id="CAM-02", name="Row B", location="Jalan Limau Manis", clip="case-2.mp4", analyse=True,
        exits={"up": "Gate B"}, compass={"up": "north"},
    )


@pytest.fixture
def hub() -> FakeHub:
    return FakeHub()


@pytest.fixture
def service(tmp_path: Path, hub: FakeHub) -> IncidentService:
    async def on_change(incident):
        await hub.broadcast({"type": "incident.updated", "incident": incident.model_dump(mode="json")})

    return IncidentService(IncidentStore(tmp_path / "i.db"), tmp_path / "snaps", on_change)


def make_pipeline(camera, tmp_path, service, hub, source, trigger=None, verifier=None, detector=None, control=None,
                  **settings):
    return CameraPipeline(
        camera, Settings(_env_file=None, data_dir=tmp_path, **settings), detector or FakeDetector(),
        trigger or FakeTrigger(), verifier or MockVerifier(tmp_path / "none"), service, hub, FrameBuffer(),
        source=source, control=control,
    )


async def test_pipeline_candidate_creates_incident_and_verifies(camera, tmp_path, service, hub):
    pipe = make_pipeline(camera, tmp_path, service, hub, make_source(30))
    await pipe.run()
    incidents = service.store.list()
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.status is S.PENDING_REVIEW
    assert inc.verification is not None and inc.verification.is_incident
    assert inc.clip_file == "case-2.mp4"
    assert inc.candidate.suspect_track_ids == [3]
    assert len(inc.snapshot_files) == 1 and (tmp_path / "snaps" / inc.snapshot_files[0]).exists()
    updates = hub.of_type("incident.updated")
    assert [u["incident"]["status"] for u in updates] == ["CANDIDATE", "PENDING_REVIEW"]


async def test_pipeline_broadcasts_detections_sync_and_suspect_flags(camera, tmp_path, service, hub):
    await make_pipeline(camera, tmp_path, service, hub, make_source(30)).run()
    dets = hub.of_type("detections")
    assert len(dets) == 30
    first, last = dets[0], dets[-1]
    assert set(first) >= {"camera_id", "loop", "pts", "frame_w", "frame_h", "tracks"}
    assert all(t["suspect"] is False for t in first["tracks"])  # before the candidate
    flagged = {t["id"] for t in last["tracks"] if t["suspect"]}
    assert flagged == {2, 3}  # rider + motorcycle of the open incident
    assert "keypoints" not in last["tracks"][0]
    syncs = hub.of_type("camera.sync")
    assert len(syncs) >= 3 and set(syncs[0]) >= {"camera_id", "loop", "pts", "wall_time"}


@pytest.mark.parametrize("exc", [VerificationUnavailable("timed out"), RuntimeError("boom")])
async def test_pipeline_verifier_failure_still_pending_review(camera, tmp_path, service, hub, exc):
    pipe = make_pipeline(camera, tmp_path, service, hub, make_source(30), verifier=RaisingVerifier(exc))
    await pipe.run()
    inc = service.store.list()[0]
    assert inc.status is S.PENDING_REVIEW
    assert inc.verification is None
    assert "AI verification unavailable" in inc.verification_error


async def test_pipeline_loop_change_resets_components(camera, tmp_path, service, hub):
    det, trig = FakeDetector(), FakeTrigger(fire_on_call=None)
    buf_pipe = make_pipeline(camera, tmp_path, service, hub, make_source(5, loops=(0, 1)), trigger=trig, detector=det)
    await buf_pipe.run()
    assert det.resets == 1 and trig.resets == 1
    assert len(buf_pipe.buffer) == 5  # cleared at the wrap, then 5 new frames
    assert [d["loop"] for d in hub.of_type("detections")] == [0] * 5 + [1] * 5
    assert service.store.list() == []


async def test_pipeline_suspect_flags_cleared_after_loop_change(camera, tmp_path, service, hub):
    trig = FakeTrigger(fire_on_call=3)
    await make_pipeline(camera, tmp_path, service, hub, make_source(5, loops=(0, 1)), trigger=trig).run()
    dets = hub.of_type("detections")
    loop1 = [d for d in dets if d["loop"] == 1]
    assert any(t["suspect"] for d in dets if d["loop"] == 0 for t in d["tracks"])
    assert not any(t["suspect"] for t in loop1[0]["tracks"])  # track IDs restart on wrap: flags must too


async def test_analyse_fps_skips_frames(camera, tmp_path, service, hub):
    det, trig = FakeDetector(), FakeTrigger(fire_on_call=None)
    pipe = make_pipeline(camera, tmp_path, service, hub, make_source(30, fps=30), trigger=trig, detector=det,
                         analyse_fps=10.0)
    await pipe.run()
    assert det.calls == 10 and trig.calls == 10  # every 3rd frame of a 30 fps source
    assert len(pipe.buffer) == 30  # skipped frames are still buffered, so keyframes stay smooth
    assert len(hub.of_type("detections")) == 10
    assert [round(d["pts"], 3) for d in hub.of_type("detections")][:3] == [0.0, 0.1, 0.2]


async def test_analyse_fps_none_analyses_every_frame(camera, tmp_path, service, hub):
    det = FakeDetector()
    await make_pipeline(camera, tmp_path, service, hub, make_source(30, fps=30), detector=det).run()
    assert det.calls == 30


async def test_analyse_fps_restarts_at_loop_wrap(camera, tmp_path, service, hub):
    det = FakeDetector()
    await make_pipeline(camera, tmp_path, service, hub, make_source(6, fps=30, loops=(0, 1)),
                        trigger=FakeTrigger(fire_on_call=None), detector=det, analyse_fps=10.0).run()
    assert det.calls == 4  # frames 0 and 3 of each loop; pts restarts at 0 so loop 1 is analysed again


# ---- replay ------------------------------------------------------------------------------


def write_precomputed(dir_: Path, camera: CameraConfig, with_candidate: bool = True) -> Path:
    import cv2

    dir_.mkdir(parents=True, exist_ok=True)
    frames = [
        FakeDetector().process(None, camera.id, i / 10, 0).model_dump(mode="json") for i in range(30)
    ]
    cand = CandidateEvent(
        camera_id=camera.id, pts=1.0, loop=0, trigger="rule", suspect_track_ids=[3], victim_track_id=1,
        motorcycle_track_id=2, detected_at=datetime.now(timezone.utc),
    )
    verification = VerificationResult(
        is_incident=True, incident_type="snatch_theft", confidence=0.9, summary="x",
        suspects=[PersonDesc(track_id=3, description="rider")], escape_direction="north",
    )
    data = {
        "fps": 10.0,
        "frames": frames,
        "candidates": [
            {
                "candidate": cand.model_dump(mode="json"),
                "verification": verification.model_dump(mode="json"),
                "direction": ["north", "Gate B"],
            }
        ] if with_candidate else [],
    }
    path = dir_ / f"{camera.id}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    cv2.imwrite(str(dir_ / f"{camera.id}_3.jpg"), np.full((40, 40, 3), 200, dtype=np.uint8))
    return path


async def test_replay_emits_same_message_types_as_live(camera, tmp_path, service, hub):
    live_hub = FakeHub()
    live_service = IncidentService(
        IncidentStore(tmp_path / "live.db"), tmp_path / "live_snaps",
        lambda inc: live_hub.broadcast({"type": "incident.updated", "incident": inc.model_dump(mode="json")}),
    )
    await make_pipeline(camera, tmp_path, live_service, live_hub, make_source(30)).run()

    path = write_precomputed(tmp_path / "precomputed", camera)
    replay = ReplayPipeline(camera, path, service, hub, realtime=False, max_loops=1, verify_delay=0.0)
    await replay.run()

    assert {m["type"] for m in hub.messages} == {m["type"] for m in live_hub.messages}
    assert set(hub.of_type("detections")[0]) == set(live_hub.of_type("detections")[0])
    assert set(hub.of_type("camera.sync")[0]) == set(live_hub.of_type("camera.sync")[0])
    inc = service.store.list()[0]
    assert inc.status is S.PENDING_REVIEW
    assert (inc.escape_direction, inc.escape_exit) == ("north", "Gate B")
    assert len(inc.snapshot_files) == 1
    assert [u["incident"]["status"] for u in hub.of_type("incident.updated")] == ["CANDIDATE", "PENDING_REVIEW"]


async def test_replay_injects_candidate_once_per_loop_and_marks_suspects(camera, tmp_path, service, hub):
    path = write_precomputed(tmp_path / "precomputed", camera)
    await ReplayPipeline(camera, path, service, hub, realtime=False, max_loops=2, verify_delay=0.0).run()
    assert len(service.store.list()) == 2  # one per loop, like the live rule after a loop reset
    dets = hub.of_type("detections")
    assert [d["loop"] for d in dets] == [0] * 30 + [1] * 30
    assert any(t["suspect"] for t in dets[29]["tracks"])
    assert not any(t["suspect"] for t in dets[0]["tracks"])
    assert not any(t["suspect"] for t in dets[30]["tracks"])  # loop 1 starts clean


# ---- suspect flags expire ------------------------------------------------------------------------
async def test_suspect_flags_expire_after_suspect_flag_s(camera, tmp_path, service, hub):
    # candidate on the 10th frame (pts 0.9); flagged for 1 s, so frames after pts 1.9 are clean again
    pipe = make_pipeline(camera, tmp_path, service, hub, make_source(60), suspect_flag_s=1.0)
    await pipe.run()
    dets = hub.of_type("detections")
    flagged = [d["pts"] for d in dets if any(t["suspect"] for t in d["tracks"])]
    assert flagged and min(flagged) >= 0.9 - 1e-6  # nothing is flagged before the candidate
    assert max(flagged) <= 1.9 + 1e-6              # and it stops: bystanders who walk up later stay unflagged
    assert not any(t["suspect"] for t in dets[-1]["tracks"])


async def test_replay_suspect_flags_expire_too(camera, tmp_path, service, hub):
    path = write_precomputed(tmp_path / "precomputed", camera)  # candidate at pts 1.0, clip is 3 s
    await ReplayPipeline(camera, path, service, hub, realtime=False, max_loops=1, verify_delay=0.0,
                         suspect_flag_s=0.5).run()
    dets = hub.of_type("detections")
    # the candidate (pts 1.0) is injected after that frame is sent, so flags start on frame 11 and last 0.5 s
    assert any(t["suspect"] for t in dets[12]["tracks"])
    assert not any(t["suspect"] for t in dets[29]["tracks"])
