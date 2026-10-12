"""How many cameras can one GPU analyse? Runs N simultaneous camera pipelines for each N and stops at
the first N that cannot keep up.

    uv run python scripts/scale_test.py --clip data/case-2.mp4 --max-cameras 16 --seconds 60 --analyse-fps 10

Each N runs in a fresh subprocess (no state or GPU memory leaks between runs) that the parent kills on a
timeout. Writes backend/reports/scale.json. The pipelines use the Rule B trigger and the dry-run (mock)
verifier, because this measures GPU capacity, not AI quality.
"""
import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BACKEND_DIR, CameraConfig, Settings  # noqa: E402
from scripts.report_meta import git_commit, utc_now  # noqa: E402

REPORTS_DIR = BACKEND_DIR / "reports"
CAMERA_COUNTS = [1, 2, 4, 8, 12, 16]
MEAN_FPS_FRACTION = 0.9  # stop when the mean per-camera fps falls below this share of the target
LAG_LIMIT_S = 1.0  # ... or when the p90 frame lag exceeds this
WARMUP_S = 3.0  # first calls (CUDA init, cudnn autotune) are not representative
WORKER_GRACE_S = 60.0
ROW_PREFIX = "SCALE_ROW "


def is_oom(exc: BaseException) -> bool:
    return type(exc).__name__.endswith("OutOfMemoryError") or "out of memory" in str(exc).lower()


def stop_reason(row: dict, target_fps: float) -> str | None:
    """Why this N is not OK, or None when it is."""
    if row.get("oom"):
        return f"CUDA out of memory at N={row['n']}"
    if row.get("error"):
        return f"N={row['n']} failed: {row['error']}"
    if row["fps_mean"] < MEAN_FPS_FRACTION * target_fps - 1e-9:
        return f"mean fps {row['fps_mean']:.1f} < {MEAN_FPS_FRACTION} x target {target_fps:g} at N={row['n']}"
    if row["lag_p90_s"] > LAG_LIMIT_S:
        return f"p90 lag {row['lag_p90_s']:.2f}s > {LAG_LIMIT_S:g}s at N={row['n']}"
    return None


def run_scale(
    counts: list[int], runner: Callable[[int], dict], target_fps: float
) -> tuple[list[dict], int, str | None]:
    """Runs `runner(n)` for each N until one fails. Returns (rows, max_cameras_ok, why it stopped)."""
    rows: list[dict] = []
    max_ok, reason = 0, None
    for n in counts:
        try:
            row = runner(n)
        except Exception as exc:  # noqa: BLE001 - a dead worker is a result, not a crash of the report
            row = {"n": n, "fps_mean": None, "fps_min": None, "lag_p90_s": None, "gpu_mem_gb": None}
            row["error"] = str(exc)
            if is_oom(exc):
                row["oom"] = True
        reason = stop_reason(row, target_fps)
        row["ok"] = reason is None
        rows.append(row)
        if reason is not None:
            break
        max_ok = n
    return rows, max_ok, reason


def build_report(
    rows: list[dict], max_ok: int, reason: str | None, target_fps: float, clip: str, seconds: float,
    analyse_fps: float | None,
) -> dict:
    gpu = None
    try:
        import torch

        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:  # noqa: BLE001
        pass
    return {
        "meta": {
            "commit": git_commit(),
            "generated_at": utc_now(),
            "triggers": "rule",
            "verifier": "dry-run",
            "model": None,
            "threshold": None,
            "clip": clip,
            "clips": [clip],
            "sources": [],
            "seconds": seconds,
            "analyse_fps": analyse_fps,
            "gpu": gpu,
        },
        "target_fps": target_fps,
        "rows": rows,
        "max_cameras_ok": max_ok,
        "stopped_reason": reason,
    }


def summarise(samples: dict[int, list[tuple[float, float]]], warmup_s: float = WARMUP_S) -> dict:
    """samples: camera -> [(seconds since start, lag seconds)] per analysed frame."""
    fps: list[float] = []
    lags: list[float] = []
    for pts in samples.values():
        kept = [(t, lag) for t, lag in pts if t >= warmup_s]
        lags += [lag for _, lag in kept]
        span = kept[-1][0] - kept[0][0] if len(kept) >= 2 else 0.0
        fps.append((len(kept) - 1) / span if span > 0 else 0.0)
    return {
        "fps_mean": float(np.mean(fps)) if fps else 0.0,
        "fps_min": float(min(fps)) if fps else 0.0,
        "lag_p90_s": float(np.percentile(lags, 90)) if lags else float("inf"),
        "cameras_running": sum(1 for f in fps if f > 0),
    }


class _Metered:
    """Wraps a detector: records when each analysed frame finished and how far behind the clip clock it was."""

    def __init__(self, inner, index: int, source, samples: dict[int, list], t0: float):
        self.inner, self.index, self.source, self.samples, self.t0 = inner, index, source, samples, t0

    def reset(self) -> None:
        self.inner.reset()

    def process(self, frame, camera_id, pts, loop):
        fd = self.inner.process(frame, camera_id, pts, loop)
        lag = time.time() - (self.source.start_wall_time + pts)
        self.samples[self.index].append((time.perf_counter() - self.t0, max(0.0, lag)))
        return fd


class _NullHub:
    async def broadcast(self, msg: dict) -> None:
        pass


async def _run_pipelines(pipelines: list, seconds: float) -> list[BaseException]:
    tasks = [asyncio.create_task(p.run()) for p in pipelines]
    await asyncio.wait(tasks, timeout=seconds)  # a task that ended early failed (the clip loops forever)
    errors = [t.exception() for t in tasks if t.done() and not t.cancelled() and t.exception()]
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    return errors


def measure(
    n: int,
    clip: Path,
    seconds: float,
    analyse_fps: float | None,
    detector_factory: Callable[[], object] | None = None,
    warmup_s: float = WARMUP_S,
) -> dict:
    """Runs n camera pipelines on one clip for `seconds` in this process and returns one report row."""
    from app.incidents.service import IncidentService
    from app.incidents.store import IncidentStore
    from app.pipeline import CameraPipeline
    from app.trigger import make_trigger
    from app.verify.mock_verifier import MockVerifier
    from app.video.buffer import FrameBuffer
    from app.video.source import ClipSource

    try:
        import torch

        cuda = torch.cuda.is_available()
    except ImportError:
        torch, cuda = None, False
    if cuda:
        torch.cuda.reset_peak_memory_stats()

    if detector_factory is None:
        from app.detect.detector import Detector

        detector_factory = Detector
    tmp = Path(tempfile.mkdtemp(prefix="scale_"))
    settings = Settings(_env_file=None, triggers="rule", analyse_fps=analyse_fps, data_dir=tmp, db_path=tmp / "i.db")

    async def noop(_incident) -> None:
        pass

    service = IncidentService(IncidentStore(settings.db_path), tmp / "snaps", noop)
    samples: dict[int, list] = {i: [] for i in range(n)}
    t0 = time.perf_counter()
    pipelines = []
    for i in range(n):
        camera = CameraConfig(id=f"SCALE-{i:02d}", name=f"Scale {i}", location="gpu", clip=Path(clip).name, analyse=True)
        source = ClipSource(clip, realtime=True)
        buffer = FrameBuffer()
        detector = _Metered(detector_factory(), i, source, samples, t0)
        pipelines.append(CameraPipeline(camera, settings, detector, make_trigger(settings, camera, buffer),
                                        MockVerifier(tmp / "none"), service, _NullHub(), buffer, source=source))
    t0 = time.perf_counter()  # the clock starts after the models are loaded
    for m in (p.detector for p in pipelines):
        m.t0 = t0
    errors = asyncio.run(_run_pipelines(pipelines, seconds))

    row = {"n": n, **summarise(samples, warmup_s if seconds > 2 * warmup_s else 0.0)}
    row["gpu_mem_gb"] = torch.cuda.max_memory_allocated() / 1e9 if cuda else 0.0
    oom = [e for e in errors if is_oom(e)]
    if oom:
        if cuda:
            torch.cuda.empty_cache()
        row.update(oom=True, error=str(oom[0]))
    elif errors:
        row["error"] = f"pipeline crashed: {errors[0]!r}"
    return row


def subprocess_runner(clip: Path, seconds: float, analyse_fps: float | None) -> Callable[[int], dict]:
    def run(n: int) -> dict:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", "--n", str(n), "--clip", str(clip),
               "--seconds", str(seconds)]
        if analyse_fps:
            cmd += ["--analyse-fps", str(analyse_fps)]
        timeout = seconds + WORKER_GRACE_S + 4 * n  # model loading grows with n
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise TimeoutError(f"worker for N={n} exceeded {timeout:.0f}s and was killed") from None
        for line in reversed(out.splitlines()):
            if line.startswith(ROW_PREFIX):
                return json.loads(line[len(ROW_PREFIX):])
        tail = " | ".join(err.strip().splitlines()[-3:])
        if "out of memory" in err.lower():
            raise MemoryError(f"CUDA out of memory (worker exit {proc.returncode}): {tail}")
        raise RuntimeError(f"worker for N={n} exited {proc.returncode} without a result: {tail}")

    return run


def _clip_fps(clip: Path) -> float:
    import cv2

    cap = cv2.VideoCapture(str(clip))
    try:
        return cap.get(cv2.CAP_PROP_FPS) or 25.0
    finally:
        cap.release()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--clip", type=Path, required=True)
    ap.add_argument("--max-cameras", type=int, default=16)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--analyse-fps", type=float, default=None)
    ap.add_argument("--out", type=Path, default=REPORTS_DIR / "scale.json")
    ap.add_argument("--worker", action="store_true", help="internal: run one N and print its row")
    ap.add_argument("--n", type=int, default=1, help="internal: cameras for --worker")
    a = ap.parse_args()

    if a.worker:
        try:
            row = measure(a.n, a.clip, a.seconds, a.analyse_fps)
        except Exception as exc:  # noqa: BLE001
            if not is_oom(exc):
                raise
            try:
                import torch

                torch.cuda.empty_cache()
            except ImportError:
                pass
            row = {"n": a.n, "fps_mean": None, "fps_min": None, "lag_p90_s": None, "gpu_mem_gb": None,
                   "oom": True, "error": str(exc)}
        print(ROW_PREFIX + json.dumps(row))
        return 0

    clip_fps = _clip_fps(a.clip)
    target = min(a.analyse_fps, clip_fps) if a.analyse_fps else clip_fps
    counts = [n for n in CAMERA_COUNTS if n <= a.max_cameras]
    print(f"clip {a.clip.name} at {clip_fps:g} fps, target {target:g} fps per camera, N in {counts}")
    rows, max_ok, reason = run_scale(counts, subprocess_runner(a.clip, a.seconds, a.analyse_fps), target)
    for r in rows:
        print(f"  N={r['n']:>2}: fps mean={r['fps_mean']} min={r['fps_min']} lag p90={r['lag_p90_s']} "
              f"gpu={r['gpu_mem_gb']} GB {'OK' if r['ok'] else 'STOP'}")
    report = build_report(rows, max_ok, reason, target, a.clip.name, a.seconds, a.analyse_fps)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"max cameras OK: {max_ok}" + (f" (stopped: {reason})" if reason else "") + f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
