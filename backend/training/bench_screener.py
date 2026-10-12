"""Benchmark the Gemini Step 1 screener on labelled videos.

    uv run python -m training.bench_screener --split val     # also picks and saves the threshold
    uv run python -m training.bench_screener --split test    # reads the saved threshold

Each video is stepped through every --stride-s seconds; at each step 6 frames from the last 3 s are
sent to the screener (no YOLO boxes drawn). Calls are cached in a JSONL file so changing only the
threshold costs nothing, and the run refuses to start if it would make more than --max-calls new calls.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from app.config import DATA_DIR, BACKEND_DIR, CameraConfig, Settings, load_cameras
from app.trigger.gemini_screener import GeminiScreener, ScreenResult, ScreenUnavailable, build_screen_prompt
from training.events import NO_SCORE, VideoScores, choose_threshold, event_hits, wilson_interval
from training.labels import DATASETS_DIR, LABELS_PATH, LabelRow, read_labels, video_duration
from training.splits import assert_no_demo_clips, split_sources

WINDOW_S = 3.0
N_FRAMES = 6
MAX_WIDTH = 640
HIT_KWARGS = dict(consecutive=1, tolerance_s=3.0)  # a score at time t describes the window ending at t
BENCH_CAMERA = CameraConfig(id="BENCH", name="Street CCTV camera", location="public street")
REPORTS_DIR = BACKEND_DIR / "reports"


class BenchmarkIncomplete(Exception):
    """Some screening calls failed, so the numbers (and any threshold) would be misleading."""


def step_score(result: ScreenResult) -> float:
    return result.score if result.suspicious else NO_SCORE


class TooManyCalls(Exception):
    def __init__(self, planned: int, limit: int):
        super().__init__(f"{planned} new Gemini calls planned, limit is {limit} (raise --max-calls)")
        self.planned, self.limit = planned, limit


def _step_times(duration: float, stride_s: float) -> list[float]:
    if duration < WINDOW_S:
        return [duration]
    times, t = [], WINDOW_S
    while t <= duration + 1e-9:
        times.append(round(t, 3))
        t += stride_s
    return times


def _read_jpegs(cap: cv2.VideoCapture, fps: float, end_t: float) -> list[bytes] | None:
    out: list[bytes] = []
    for t in np.linspace(max(0.0, end_t - WINDOW_S), end_t, N_FRAMES):
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(t * fps) - (1 if t >= end_t else 0)))
        ok, frame = cap.read()
        if not ok:
            return None
        if frame.shape[1] > MAX_WIDTH:
            scale = MAX_WIDTH / frame.shape[1]
            frame = cv2.resize(frame, (MAX_WIDTH, max(1, round(frame.shape[0] * scale))), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return None
        out.append(buf.tobytes())
    return out


def _load_cache(path: Path) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                cache[rec["key"]] = rec["result"]
    return cache


def run(
    split: str,
    screener,
    labels: Path = LABELS_PATH,
    datasets_dir: Path = DATASETS_DIR,
    cameras: list[CameraConfig] | None = None,
    data_dir: Path = DATA_DIR,
    cache_path: Path = REPORTS_DIR / "screener_cache.jsonl",
    out_path: Path | None = None,
    threshold_path: Path = REPORTS_DIR / "screener_threshold.json",
    splits_path: Path = REPORTS_DIR / "splits.json",
    stride_s: float = 3.0,
    max_calls: int = 1500,
) -> dict:
    if split not in ("val", "test", "all"):
        raise ValueError("split must be val, test or all")
    threshold_path, cache_path = Path(threshold_path), Path(cache_path)
    out_path = Path(out_path) if out_path else REPORTS_DIR / f"screener_{split}.json"
    saved: dict | None = None
    if split == "test":
        if not threshold_path.exists():
            raise FileNotFoundError(f"{threshold_path} missing: run --split val first")
        saved = json.loads(threshold_path.read_text(encoding="utf-8"))

    rows = read_labels(labels)
    cameras = cameras if cameras is not None else load_cameras(Path(data_dir) / "cameras.json")
    assert_no_demo_clips(rows, cameras, data_dir)
    splits_path = Path(splits_path)
    existing = json.loads(splits_path.read_text(encoding="utf-8")) if splits_path.exists() else {}
    mapping = split_sources(rows, existing=existing)
    if split != "all":  # keep every source in the split it was first given
        splits_path.parent.mkdir(parents=True, exist_ok=True)
        splits_path.write_text(json.dumps({**existing, **mapping}, indent=2, sort_keys=True), encoding="utf-8")
    chosen = [r for r in rows if split == "all" or mapping[r.source_id] == split]
    by_file: dict[str, list[LabelRow]] = {}
    for r in chosen:
        by_file.setdefault(r.file, []).append(r)

    model = getattr(screener, "model", "unknown")
    prompt_hash = hashlib.sha1(build_screen_prompt(BENCH_CAMERA).encode()).hexdigest()[:8]
    cache = _load_cache(cache_path)
    if saved is not None and (saved.get("model") != model or saved.get("prompt_hash") != prompt_hash):
        raise ValueError(
            f"{threshold_path.name} was chosen with model {saved.get('model')} / prompt {saved.get('prompt_hash')}, "
            f"now {model} / {prompt_hash}: rerun --split val"
        )
    saved_threshold = saved["threshold"] if saved else None

    def key(file: str, t: float) -> str:
        return hashlib.sha1(f"{file}|{t:.3f}|{model}|{prompt_hash}".encode()).hexdigest()

    plan: dict[str, tuple[float, list[float]]] = {}
    new_calls = 0
    for file in by_file:
        duration = video_duration(Path(datasets_dir) / file)
        times = _step_times(duration, stride_s)
        plan[file] = (duration, times)
        new_calls += sum(1 for t in times if key(file, t) not in cache)
    print(f"{sum(len(t) for _, t in plan.values())} steps, {new_calls} new Gemini calls, "
          f"{len(by_file)} videos in split '{split}'")
    if new_calls > max_calls:
        raise TooManyCalls(new_calls, max_calls)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    calls = cache_hits = errors = 0
    videos: list[VideoScores] = []
    detail: dict[str, tuple[list[tuple[float, float]], list[tuple[float, float]]]] = {}
    with cache_path.open("a", encoding="utf-8") as cache_file:
        for file, (duration, times) in plan.items():
            events = [(r.start, r.end) for r in by_file[file] if r.label == "snatch"]
            cap = cv2.VideoCapture(str(Path(datasets_dir) / file))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            scores: list[tuple[float, float]] = []
            for t in times:
                k = key(file, t)
                if k in cache:
                    cache_hits += 1
                    result = ScreenResult.model_validate(cache[k])
                else:
                    frames = _read_jpegs(cap, fps, t)
                    if frames is None:
                        continue
                    try:
                        result = screener.screen(frames, BENCH_CAMERA)
                    except ScreenUnavailable as exc:
                        errors += 1  # not scored: a failed call is missing data, not a negative
                        print(f"  screen failed at {file}@{t}: {exc}", file=sys.stderr)
                        continue
                    calls += 1
                    cache_file.write(json.dumps({"key": k, "result": result.model_dump()}) + "\n")
                    cache_file.flush()
                scores.append((t, step_score(result)))
            cap.release()
            non_event_hours = max(0.0, duration - sum(b - a for a, b in events)) / 3600
            videos.append((scores, events, non_event_hours))
            detail[file] = (scores, events)

    failed = f"{errors} screening calls failed; rerun to retry them (successful calls are cached)"
    if errors and split == "val":
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"split": split, "model": model, "errors": errors, "calls": calls,
                                        "cache_hits": cache_hits}, indent=2), encoding="utf-8")
        raise BenchmarkIncomplete(f"{failed}; no threshold saved")

    threshold = saved_threshold
    if split == "val":
        threshold = choose_threshold(videos, **HIT_KWARGS)
        threshold_path.parent.mkdir(parents=True, exist_ok=True)
        threshold_path.write_text(
            json.dumps({"threshold": threshold, "model": model, "prompt_hash": prompt_hash}, indent=2),
            encoding="utf-8")
    if threshold is None:  # split == "all": smoke run
        threshold = Settings(_env_file=None).screen_threshold

    hits = false = n_events = 0
    hours = 0.0
    missed: list[dict] = []
    for scores, events, h in videos:
        hit, f = event_hits(scores, events, threshold, **HIT_KWARGS)
        hits, false, n_events, hours = hits + hit, false + f, n_events + len(events), hours + h
    for file, (scores, events) in detail.items():
        for a, b in events:
            if event_hits(scores, [(a, b)], threshold, **HIT_KWARGS)[0] == 0:
                near = [s for t, s in scores if a - 3.0 <= t <= b + 3.0]
                missed.append({"file": file, "start": a, "end": b, "best_score": max(near, default=0.0)})
    lo, hi = wilson_interval(hits, n_events)
    report = {
        "split": split, "model": model, "prompt_hash": prompt_hash, "threshold": threshold,
        "events": n_events, "hits": hits, "event_recall": hits / n_events if n_events else None,
        "recall_ci95": [lo, hi], "non_event_hours": hours, "false_triggers": false,
        "false_triggers_per_hour": false / hours if hours else None,
        "calls": calls, "cache_hits": cache_hits, "errors": errors,
        "rows_by_origin": dict(Counter(r.origin for r in chosen)), "missed": missed,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "missed"}, indent=2))
    if errors and split == "test":
        raise BenchmarkIncomplete(f"{failed}; the report was written but its numbers are incomplete")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--labels", type=Path, default=LABELS_PATH)
    ap.add_argument("--split", choices=["val", "test", "all"], required=True,
                    help="'all' is only for smoke runs; do not report it")
    ap.add_argument("--stride-s", type=float, default=3.0)
    ap.add_argument("--max-calls", type=int, default=1500)
    ap.add_argument("--cache", type=Path, default=REPORTS_DIR / "screener_cache.jsonl")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    settings = Settings()
    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set")
        return 1
    try:
        run(a.split, GeminiScreener(settings, timeout_s=20.0), labels=a.labels, cache_path=a.cache,
            out_path=a.out, stride_s=a.stride_s, max_calls=a.max_calls)
    except TooManyCalls as exc:
        print(exc)
        return 2
    except (BenchmarkIncomplete, ValueError) as exc:
        print(exc)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
