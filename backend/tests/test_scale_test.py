import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.models import FrameDetections, Track
from scripts.scale_test import (
    LAG_LIMIT_S,
    MEAN_FPS_FRACTION,
    build_report,
    measure,
    run_scale,
    stop_reason,
    summarise,
)


def row(n: int, fps_mean: float = 10.0, lag_p90_s: float = 0.1, **kw) -> dict:
    return {"n": n, "fps_mean": fps_mean, "fps_min": fps_mean - 0.5, "lag_p90_s": lag_p90_s, "gpu_mem_gb": 1.0,
            **kw}


# ---- stop rule -------------------------------------------------------------------------------
def test_scale_stop_rule_on_low_fps():
    assert stop_reason(row(4, fps_mean=10.0), target_fps=10.0) is None
    assert stop_reason(row(4, fps_mean=9.0), target_fps=10.0) is None  # exactly 0.9 x target still passes
    assert "fps" in stop_reason(row(8, fps_mean=8.9), target_fps=10.0)
    assert MEAN_FPS_FRACTION == 0.9
    runs = []

    def runner(n: int) -> dict:
        runs.append(n)
        return row(n, fps_mean=10.0 if n <= 2 else 4.0)

    rows, max_ok, reason = run_scale([1, 2, 4, 8, 12, 16], runner, target_fps=10.0)
    assert runs == [1, 2, 4]  # stops at the first failing N, never tries 8, 12, 16
    assert [r["ok"] for r in rows] == [True, True, False]
    assert max_ok == 2 and "fps" in reason


def test_scale_stop_on_lag():
    assert LAG_LIMIT_S == 1.0
    assert "lag" in stop_reason(row(4, lag_p90_s=1.5), target_fps=10.0)
    rows, max_ok, _ = run_scale([1, 2], lambda n: row(n, lag_p90_s=2.0 if n == 2 else 0.1), target_fps=10.0)
    assert max_ok == 1 and rows[-1]["ok"] is False


class FakeOom(Exception):
    pass


FakeOom.__name__ = "OutOfMemoryError"


def test_scale_stop_rule_on_oom():
    def runner(n: int) -> dict:
        if n >= 4:
            raise FakeOom("CUDA out of memory. Tried to allocate 2.00 GiB")
        return row(n)

    rows, max_ok, reason = run_scale([1, 2, 4, 8], runner, target_fps=10.0)
    assert [r["n"] for r in rows] == [1, 2, 4]  # 8 never attempted
    assert rows[-1]["oom"] is True and rows[-1]["ok"] is False
    assert max_ok == 2 and "out of memory" in reason.lower()


def test_scale_worker_crash_or_timeout_stops_cleanly():
    def runner(n: int) -> dict:
        if n == 2:
            raise TimeoutError("worker exceeded 120s and was killed")
        return row(n)

    rows, max_ok, reason = run_scale([1, 2, 4], runner, target_fps=10.0)
    assert [r["n"] for r in rows] == [1, 2]
    assert rows[-1]["ok"] is False and "killed" in rows[-1]["error"]
    assert max_ok == 1 and "killed" in reason


def test_scale_never_ok_gives_zero():
    _, max_ok, _ = run_scale([1, 2], lambda n: row(n, fps_mean=1.0), target_fps=10.0)
    assert max_ok == 0


def test_scale_all_ok_has_no_stop_reason():
    rows, max_ok, reason = run_scale([1, 2], lambda n: row(n), target_fps=10.0)
    assert max_ok == 2 and reason is None and all(r["ok"] for r in rows)


# ---- report ----------------------------------------------------------------------------------
def test_scale_report_schema():
    rows, max_ok, reason = run_scale([1, 2], lambda n: row(n), target_fps=10.0)
    report = build_report(rows, max_ok, reason, target_fps=10.0, clip="case-2.mp4", seconds=60, analyse_fps=10.0)
    assert set(report) >= {"meta", "target_fps", "rows", "max_cameras_ok", "stopped_reason"}
    assert set(report["rows"][0]) >= {"n", "fps_mean", "fps_min", "lag_p90_s", "gpu_mem_gb", "ok"}
    assert report["meta"]["clip"] == "case-2.mp4" and report["meta"]["analyse_fps"] == 10.0
    assert report["meta"]["verifier"] == "dry-run" and report["meta"]["triggers"] == "rule"
    assert report["meta"]["commit"] and report["meta"]["generated_at"]
    json.dumps(report)  # serialisable


# ---- measurement -----------------------------------------------------------------------------
def test_summarise_fps_and_lag():
    # camera 0: 10 detections one second apart-ish over 1 s; camera 1: 5 detections
    samples = {
        0: [(0.1 * i, 0.05) for i in range(11)],  # (t, lag_s): 10 intervals in 1.0 s -> 10 fps
        1: [(0.2 * i, 0.5) for i in range(6)],  # 5 intervals in 1.0 s -> 5 fps
    }
    s = summarise(samples, warmup_s=0.0)
    assert s["fps_mean"] == pytest.approx(7.5)
    assert s["fps_min"] == pytest.approx(5.0)
    assert s["lag_p90_s"] == pytest.approx(0.5)


def test_summarise_ignores_warmup_samples():
    samples = {0: [(0.0, 5.0)] + [(3.0 + 0.1 * i, 0.05) for i in range(11)]}
    s = summarise(samples, warmup_s=2.0)
    assert s["lag_p90_s"] == pytest.approx(0.05)  # the slow first call is excluded
    assert s["fps_mean"] == pytest.approx(10.0)


class FastDetector:
    def reset(self) -> None:
        pass

    def process(self, frame, camera_id, pts, loop) -> FrameDetections:
        return FrameDetections(
            camera_id=camera_id, pts=pts, frame_w=64, frame_h=48,
            tracks=[Track(id=1, cls="person", bbox=(1.0, 1.0, 20.0, 40.0), conf=0.9)], loop=loop,
        )


def test_measure_runs_n_pipelines_with_frame_skip(tmp_path):
    clip = tmp_path / "c.mp4"
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (64, 48))
    for i in range(60):
        writer.write(np.full((48, 64, 3), i, dtype=np.uint8))
    writer.release()
    r = measure(2, clip, seconds=3.0, analyse_fps=10.0, detector_factory=FastDetector, warmup_s=0.5)
    assert r["n"] == 2 and r["cameras_running"] == 2
    assert 7.0 <= r["fps_mean"] <= 10.5  # paced at the 30 fps clip clock, analysed at 10 fps
    assert r["lag_p90_s"] < 0.5
    assert "gpu_mem_gb" in r


# ---- review fixes ----------------------------------------------------------------------------
def test_summarise_with_no_samples_has_no_lag_instead_of_infinity():
    s = summarise({0: [], 1: []}, warmup_s=0.0)
    assert s["fps_mean"] == 0.0 and s["lag_p90_s"] is None
    json.dumps(s, allow_nan=False)  # Infinity is not JSON: it would make GET /api/reports fail


def test_stop_reason_when_nothing_was_analysed():
    reason = stop_reason(row(4, fps_mean=0.0, lag_p90_s=None), target_fps=10.0)
    assert reason is not None and "no frames" in reason
    rows, max_ok, _ = run_scale([1, 2], lambda n: row(n) if n == 1 else row(n, fps_mean=0.0, lag_p90_s=None), 10.0)
    assert max_ok == 1 and rows[-1]["ok"] is False
