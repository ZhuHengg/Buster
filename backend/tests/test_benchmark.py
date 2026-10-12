from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.config import CameraConfig, Settings
from app.models import CandidateEvent, FrameDetections, PersonDesc, Track, VerificationResult
from app.verify.base import VerificationUnavailable
from app.verify.mock_verifier import MockVerifier
from app.video.buffer import FrameBuffer
from scripts.benchmark import (
    PUSH_S,
    Components,
    SourceResult,
    aggregate,
    build_meta,
    run_demo,
    run_source,
)

CAMERA = CameraConfig(id="BENCH", name="Bench", location="lab")


def write_clip(path: Path, seconds: float = 10.0, fps: float = 10.0) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    assert writer.isOpened()
    for i in range(int(seconds * fps)):
        writer.write(np.full((48, 64, 3), (i * 7) % 255, dtype=np.uint8))
    writer.release()
    return path


class FakeDetector:
    def __init__(self):
        self.resets = 0

    def process(self, frame, camera_id, pts, loop) -> FrameDetections:
        return FrameDetections(
            camera_id=camera_id, pts=pts, frame_w=64, frame_h=48,
            tracks=[Track(id=1, cls="person", bbox=(1.0, 1.0, 20.0, 40.0), conf=0.9)], loop=loop,
        )

    def reset(self) -> None:
        self.resets += 1


class FireAt:
    """Trigger that fires once at each listed pts."""

    def __init__(self, times: list[float]):
        self.times, self.resets = sorted(times), 0

    def update(self, fd: FrameDetections) -> CandidateEvent | None:
        if self.times and fd.pts + 1e-6 >= self.times[0]:
            self.times.pop(0)
            return CandidateEvent(
                camera_id=fd.camera_id, pts=fd.pts, loop=fd.loop, trigger="rule",
                suspect_track_ids=[1], detected_at=datetime.now(timezone.utc),
            )
        return None

    def reset(self) -> None:
        self.resets += 1


def verdict(is_incident: bool) -> VerificationResult:
    return VerificationResult(
        is_incident=is_incident, incident_type="snatch_theft" if is_incident else "none", confidence=0.9,
        summary="x", suspects=[PersonDesc(track_id=1, description="rider")], escape_direction="unknown",
    )


class FakeVerifier:
    """Confirms candidates whose pts is in `confirm`; raises VerificationUnavailable for those in `fail`."""

    def __init__(self, confirm: list[float], fail: list[float] = ()):
        self.confirm, self.fail = confirm, list(fail)

    async def verify(self, candidate, keyframes, camera):
        assert keyframes, "verifier must receive keyframes"
        if any(abs(candidate.pts - t) < 0.06 for t in self.fail):
            raise VerificationUnavailable("down")
        return verdict(any(abs(candidate.pts - t) < 0.06 for t in self.confirm))


def components(fire: list[float], confirm: list[float], fail: list[float] = ()) -> Components:
    return Components(FakeDetector(), FireAt(fire), FakeVerifier(confirm, fail), FrameBuffer(), CAMERA)


def result(**kw) -> SourceResult:
    base = dict(source_id="s", hours=0.5, events=0, hits=0, final_hits=0, step1_candidates=0, step1_false=0,
                step2_confirmed=0, step2_false=0, ai_filtered=0, verify_errors=0, latencies=[])
    return SourceResult(**{**base, **kw})


# ---- aggregate -------------------------------------------------------------------------------
def test_aggregate_recall_and_false_rate():
    agg = aggregate([
        result(source_id="a", hours=0.5, events=2, hits=2, final_hits=1, step1_false=3, step2_false=1, ai_filtered=2),
        result(source_id="b", hours=1.5, events=2, hits=1, final_hits=1, step1_false=1, step2_false=1),
    ])
    assert agg["events"] == 4
    assert agg["event_recall_step1"] == pytest.approx(3 / 4)
    assert agg["event_recall_final"] == pytest.approx(2 / 4)
    assert agg["false_per_hour_step1"] == pytest.approx(4 / 2.0)
    assert agg["false_per_hour_final"] == pytest.approx(2 / 2.0)
    lo, hi = agg["event_recall_final_ci95"]
    assert lo < 0.5 < hi


def test_aggregate_without_events_or_false_triggers_gives_none_not_zero():
    agg = aggregate([result(hours=1.0)])
    assert agg["event_recall_step1"] is None and agg["event_recall_final"] is None
    assert agg["ai_filter_rate"] is None  # nothing to filter: undefined, not 100 % or 0 %
    assert agg["false_per_hour_final"] == 0.0


def test_ai_filter_rate():
    agg = aggregate([
        result(step1_false=4, step2_false=1, ai_filtered=3),
        result(step1_false=2, step2_false=2, ai_filtered=0),
    ])
    assert agg["ai_filter_rate"] == pytest.approx(3 / 6)


def test_latency_percentiles():
    lat = [{"event_to_candidate_s": float(i), "candidate_to_verified_s": 1.0, "step1_wall_s": 0.5}
           for i in (1, 2, 3, 4, 5)]
    agg = aggregate([result(events=5, hits=5, final_hits=5, latencies=lat)])
    assert agg["event_to_candidate_p50_s"] == pytest.approx(3.0)
    assert agg["event_to_candidate_p90_s"] == pytest.approx(4.6)
    assert agg["candidate_to_verified_p50_s"] == pytest.approx(1.0)
    assert agg["step1_wall_p50_s"] == pytest.approx(0.5) and agg["step1_wall_p90_s"] == pytest.approx(0.5)
    # detection -> card = event->candidate + step-1 wall time + verification + UI push
    assert agg["detection_to_card_p50_s"] == pytest.approx(3.0 + 0.5 + 1.0 + PUSH_S)
    assert PUSH_S == 0.3


def test_latency_none_without_cards():
    agg = aggregate([result(events=1)])
    assert agg["detection_to_card_p50_s"] is None and agg["event_to_candidate_p90_s"] is None
    assert agg["step1_wall_p50_s"] is None


# ---- meta ------------------------------------------------------------------------------------
def test_report_meta_includes_commit_verifier_triggers():
    s = Settings(_env_file=None, triggers="both", claude_model="claude-x", gemini_model="gem-y")
    meta = build_meta(s, MockVerifier(Path("nowhere")), threshold=0.6, sources=["a.mp4"], clips=["case-2.mp4"])
    assert meta["verifier"] == "mock"
    assert meta["triggers"] == "both"
    assert meta["threshold"] == 0.6
    assert meta["sources"] == ["a.mp4"] and meta["clips"] == ["case-2.mp4"]
    assert meta["commit"] and meta["generated_at"].endswith("+00:00")
    assert "model" in meta


# ---- run_source ------------------------------------------------------------------------------
async def test_run_source_classifies_candidates(tmp_path):
    clip = write_clip(tmp_path / "v.mp4", seconds=20)
    # event 4-6 s (window 1-9 s). candidates: 5.0 hit+confirmed, 7.0 duplicate on the same event,
    # 12.0 false and rejected by Step 2, 15.0 false and confirmed.
    comp = components(fire=[5.0, 7.0, 12.0, 15.0], confirm=[5.0, 7.0, 15.0])
    r = await run_source(clip, [(4.0, 6.0)], comp, source_id="v")
    assert (r.events, r.hits, r.final_hits) == (1, 1, 1)
    assert r.step1_candidates == 4
    assert (r.step1_false, r.step2_false, r.ai_filtered) == (2, 1, 1)
    assert r.step2_confirmed == 3
    assert r.hours == pytest.approx((20.0 - 2.0) / 3600)  # event footage is not counted as normal footage
    (lat,) = r.latencies
    assert lat["event_to_candidate_s"] == pytest.approx(1.0)  # 5.0 - event start 4.0
    assert lat["candidate_to_verified_s"] >= 0 and lat["step1_wall_s"] >= 0
    assert comp.detector.resets == 1 and comp.trigger.resets == 1


async def test_event_rejected_by_ai_is_a_step1_hit_not_a_final_hit(tmp_path):
    clip = write_clip(tmp_path / "v.mp4", seconds=10)
    r = await run_source(clip, [(4.0, 6.0)], components(fire=[5.0], confirm=[]), source_id="v")
    assert (r.hits, r.final_hits, r.step2_confirmed, r.latencies) == (1, 0, 0, [])


async def test_second_candidate_can_rescue_event_the_first_missed_at_step2(tmp_path):
    clip = write_clip(tmp_path / "v.mp4", seconds=10)
    r = await run_source(clip, [(4.0, 6.0)], components(fire=[4.5, 6.0], confirm=[6.0]), source_id="v")
    assert (r.hits, r.final_hits) == (1, 1)
    assert r.latencies[0]["event_to_candidate_s"] == pytest.approx(2.0)


async def test_verifier_unavailable_still_reaches_guard_and_is_counted(tmp_path):
    clip = write_clip(tmp_path / "v.mp4", seconds=10)
    r = await run_source(clip, [], components(fire=[3.0], confirm=[], fail=[3.0]), source_id="v")
    assert (r.step1_false, r.step2_false, r.verify_errors, r.ai_filtered) == (1, 1, 1, 0)


async def test_demo_normal_clip_counts_any_candidate_as_false(tmp_path):
    clip = write_clip(tmp_path / "normal.mp4", seconds=10)
    cams = [CameraConfig(id="CAM-07", name="n", location="l", clip="normal.mp4", analyse=True, expected_event=None)]
    out = await run_demo(cams, tmp_path, lambda cam: components(fire=[5.0], confirm=[5.0]))
    (row,) = out["per_clip"]
    assert row["camera_id"] == "CAM-07" and row["expected_event"] is None
    assert row["result"]["step1_false"] == 1 and row["result"]["step2_false"] == 1
    assert row["outcome"] == "false_alarm"


async def test_demo_snatch_clip_outcomes(tmp_path):
    write_clip(tmp_path / "snatch.mp4", seconds=10)
    cam = CameraConfig(id="CAM-02", name="n", location="l", clip="snatch.mp4", analyse=True,
                       expected_event={"start": 4.0, "end": 6.0})
    hit = await run_demo([cam], tmp_path, lambda c: components(fire=[5.0], confirm=[5.0]))
    miss = await run_demo([cam], tmp_path, lambda c: components(fire=[], confirm=[]))
    rejected = await run_demo([cam], tmp_path, lambda c: components(fire=[5.0], confirm=[]))
    assert [o["per_clip"][0]["outcome"] for o in (hit, miss, rejected)] == [
        "detected", "missed", "rejected_by_ai"]


async def test_demo_skips_cameras_without_analysis(tmp_path):
    cam = CameraConfig(id="CAM-01", name="n", location="l")
    out = await run_demo([cam], tmp_path, lambda c: components(fire=[], confirm=[]))
    assert out["per_clip"] == []
