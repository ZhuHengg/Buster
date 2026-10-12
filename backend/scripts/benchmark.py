"""End-to-end benchmark: the real pipeline (detector, Step 1 trigger, Step 2 verifier) run offline.

    uv run python scripts/benchmark.py --set both [--verifier auto|claude|gemini|mock] [--triggers rule|llm|both]

Writes backend/reports/benchmark.json as {meta, test, demo}. `test` comes from the held-out test split of
labels.csv; `demo` is reported separately and never mixed into the test numbers.

Latencies: detection is measured in VIDEO time (candidate pts minus event start) plus the wall time of the
Step 1 call (the blocking Gemini round trip); verification is wall time; the UI push is a constant.
"""
import argparse
import asyncio
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BACKEND_DIR, DATA_DIR, CameraConfig, Settings, load_cameras  # noqa: E402
from app.trigger import make_trigger  # noqa: E402
from app.trigger.base import Trigger  # noqa: E402
from app.verify.base import VerificationUnavailable, Verifier  # noqa: E402
from app.verify.mock_verifier import MockVerifier, make_verifier  # noqa: E402
from app.video.buffer import FrameBuffer  # noqa: E402
from app.video.source import ClipSource  # noqa: E402
from scripts.report_meta import git_commit, utc_now  # noqa: E402
from training.events import wilson_interval  # noqa: E402

REPORTS_DIR = BACKEND_DIR / "reports"
PUSH_S = 0.3  # candidate verified -> alert card on screen: server push + render; a documented constant
TOLERANCE_S = 3.0  # a candidate within this many seconds of a labelled event counts for it (as in bench_screener)
BENCH_CAMERA = CameraConfig(id="BENCH", name="Street CCTV camera", location="public street")


@dataclass
class Components:
    """Everything one pipeline needs, reset between sources."""

    detector: Any
    trigger: Trigger
    verifier: Verifier
    buffer: FrameBuffer
    camera: CameraConfig


class SourceResult(BaseModel):
    source_id: str
    hours: float  # footage that is NOT part of a labelled event
    events: int
    hits: int  # events with at least one Step 1 candidate
    final_hits: int  # events with at least one candidate confirmed by Step 2
    step1_candidates: int
    step1_false: int  # candidates outside every event window
    step2_confirmed: int  # all candidates Step 2 let through
    step2_false: int  # false candidates Step 2 let through (these reach the guard)
    ai_filtered: int  # false candidates Step 2 removed
    verify_errors: int  # Step 2 unavailable: the alert still reaches the guard, unverified
    latencies: list[dict]  # one per event that produced a card


async def run_source(
    path: Path, events: list[tuple[float, float]], comp: Components, source_id: str | None = None
) -> SourceResult:
    """One pass over a video: every Step 1 candidate is verified (as the live pipeline does) and judged
    against the labelled events."""
    path = Path(path)
    source = ClipSource(path, realtime=False)
    comp.detector.reset()
    comp.trigger.reset()
    comp.buffer.clear()

    # (pts, step 1 wall s, confirmed, verify error, verify wall s)
    candidates: list[tuple[float, float, bool, bool, float]] = []
    for frame, pts, loop in source:
        if loop >= 1:
            break
        fd = comp.detector.process(frame, comp.camera.id, pts, loop)
        comp.buffer.push(pts, loop, frame, fd)
        started = time.perf_counter()
        cand = comp.trigger.update(fd)
        step1_wall = time.perf_counter() - started
        if cand is None:
            continue
        keyframes = comp.buffer.keyframes(cand.pts, n=8, span=3.0)
        started = time.perf_counter()
        try:
            verdict = await comp.verifier.verify(cand, keyframes, comp.camera)
            confirmed, error = verdict.is_incident, False
        except VerificationUnavailable:
            confirmed, error = True, True  # the pipeline shows it to the guard as an unverified alert
        candidates.append((cand.pts, step1_wall, confirmed, error, time.perf_counter() - started))

    hit: dict[int, tuple] = {}
    card: dict[int, tuple] = {}
    step1_false = step2_false = ai_filtered = confirmed_n = errors = 0
    for pts, step1_wall, confirmed, error, verify_wall in candidates:
        confirmed_n += confirmed
        errors += error
        idx = next((i for i, (a, b) in enumerate(events) if a - TOLERANCE_S <= pts <= b + TOLERANCE_S), None)
        if idx is None:
            step1_false += 1
            if confirmed:
                step2_false += 1
            else:
                ai_filtered += 1
            continue
        hit.setdefault(idx, (pts, step1_wall))
        if confirmed:
            card.setdefault(idx, (pts, step1_wall, verify_wall))
    latencies = [
        {"event_to_candidate_s": pts - events[i][0], "candidate_to_verified_s": verify_wall, "step1_wall_s": wall}
        for i, (pts, wall, verify_wall) in sorted(card.items())
    ]
    event_s = sum(b - a for a, b in events)
    return SourceResult(
        source_id=source_id or path.stem,
        hours=max(0.0, source.duration - event_s) / 3600,
        events=len(events),
        hits=len(hit),
        final_hits=len(card),
        step1_candidates=len(candidates),
        step1_false=step1_false,
        step2_confirmed=confirmed_n,
        step2_false=step2_false,
        ai_filtered=ai_filtered,
        verify_errors=errors,
        latencies=latencies,
    )


def _pct(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def aggregate(results: list[SourceResult]) -> dict:
    """Totals and rates over sources. A rate with no denominator is None, never 0 or 1."""
    events = sum(r.events for r in results)
    hours = sum(r.hours for r in results)
    hits, final_hits = sum(r.hits for r in results), sum(r.final_hits for r in results)
    step1_false, step2_false = sum(r.step1_false for r in results), sum(r.step2_false for r in results)
    ai_filtered = sum(r.ai_filtered for r in results)
    lats = [lat for r in results for lat in r.latencies]
    e2c = [lat["event_to_candidate_s"] for lat in lats]
    c2v = [lat["candidate_to_verified_s"] for lat in lats]
    wall = [lat["step1_wall_s"] for lat in lats]
    total = [lat["event_to_candidate_s"] + lat["step1_wall_s"] + lat["candidate_to_verified_s"] + PUSH_S for lat in lats]
    return {
        "sources": len(results),
        "events": events,
        "non_event_hours": hours,
        "step1_hits": hits,
        "final_hits": final_hits,
        "event_recall_step1": hits / events if events else None,
        "event_recall_final": final_hits / events if events else None,
        "event_recall_final_ci95": list(wilson_interval(final_hits, events)),
        "step1_false": step1_false,
        "final_false": step2_false,
        "false_per_hour_step1": step1_false / hours if hours else None,
        "false_per_hour_final": step2_false / hours if hours else None,
        "ai_filter_rate": ai_filtered / step1_false if step1_false else None,
        "verify_errors": sum(r.verify_errors for r in results),
        "event_to_candidate_p50_s": _pct(e2c, 50),
        "event_to_candidate_p90_s": _pct(e2c, 90),
        "step1_wall_p50_s": _pct(wall, 50),
        "step1_wall_p90_s": _pct(wall, 90),
        "candidate_to_verified_p50_s": _pct(c2v, 50),
        "candidate_to_verified_p90_s": _pct(c2v, 90),
        "push_s": PUSH_S,
        "detection_to_card_p50_s": _pct(total, 50),
        "detection_to_card_p90_s": _pct(total, 90),
    }


def verifier_kind(verifier: Verifier) -> str:
    name = type(verifier).__name__
    return {"MockVerifier": "mock", "ClaudeVerifier": "claude", "GeminiVerifier": "gemini"}.get(name, name.lower())


def build_meta(settings: Settings, verifier: Verifier, threshold: float | None, sources: list[str], clips: list[str]) -> dict:
    """Everything needed to reproduce the run. `verifier` == "mock" marks the numbers as not valid evidence."""
    kind = verifier_kind(verifier)
    return {
        "commit": git_commit(),
        "generated_at": utc_now(),
        "triggers": settings.triggers,
        "verifier": kind,
        "model": {"claude": settings.claude_model, "gemini": settings.gemini_model}.get(kind),
        "screen_model": (settings.gemini_screen_model or settings.gemini_model) if settings.triggers != "rule" else None,
        "threshold": threshold,
        "sources": sources,
        "clips": clips,
    }


def _outcome(expected: bool, r: SourceResult) -> str:
    if expected:
        if r.final_hits:
            return "detected"
        return "rejected_by_ai" if r.hits else "missed"
    return "false_alarm" if r.step2_false else ("filtered_by_ai" if r.step1_false else "clean")


async def run_demo(
    cameras: list[CameraConfig], data_dir: Path, build: Callable[[CameraConfig], Components]
) -> dict:
    """The demo clips, one row each. Reported separately from the test set."""
    rows = []
    for cam in cameras:
        if not cam.analyse or not cam.clip:
            continue
        events = [(cam.expected_event.start, cam.expected_event.end)] if cam.expected_event else []
        r = await run_source(Path(data_dir) / cam.clip, events, build(cam), source_id=cam.id)
        rows.append({
            "camera_id": cam.id,
            "clip": cam.clip,
            "expected_event": cam.expected_event.model_dump() if cam.expected_event else None,
            "outcome": _outcome(bool(events), r),
            "result": r.model_dump(),
        })
    return {"per_clip": rows}


# ---- CLI ---------------------------------------------------------------------------------------
def _make_verifier(kind: str, settings: Settings) -> Verifier:
    if kind == "mock":
        return MockVerifier(settings.data_dir / "mock_verifications")
    if kind == "claude":
        if not settings.anthropic_api_key:
            raise SystemExit("--verifier claude needs ANTHROPIC_API_KEY")
        from app.verify.claude_verifier import ClaudeVerifier

        return ClaudeVerifier(settings)
    if kind == "gemini":
        if not settings.gemini_api_key:
            raise SystemExit("--verifier gemini needs GEMINI_API_KEY")
        from app.verify.gemini_verifier import GeminiVerifier

        return GeminiVerifier(settings)
    return make_verifier(settings)


def _test_sources(settings: Settings, labels: Path) -> dict[str, list[tuple[float, float]]]:
    """datasets-relative file -> snatch events, for sources in the held-out test split."""
    from training.labels import LABELS_PATH, read_labels
    from training.splits import assert_no_demo_clips, split_sources

    rows = read_labels(labels or LABELS_PATH)
    if not rows:
        return {}
    assert_no_demo_clips(rows, load_cameras(settings.data_dir / "cameras.json"), settings.data_dir)
    splits_path = REPORTS_DIR / "splits.json"
    existing = json.loads(splits_path.read_text(encoding="utf-8")) if splits_path.exists() else {}
    mapping = split_sources(rows, existing=existing)
    out: dict[str, list[tuple[float, float]]] = {}
    for r in rows:
        if mapping[r.source_id] != "test":
            continue
        out.setdefault(r.file, [])
        if r.label == "snatch":
            out[r.file].append((r.start, r.end))
    return out


async def amain(args: argparse.Namespace) -> int:
    from app.detect.detector import Detector
    from training.labels import DATASETS_DIR

    settings = Settings(_env_file=BACKEND_DIR / ".env")
    if args.triggers:
        settings = settings.model_copy(update={"triggers": args.triggers})
    saved = REPORTS_DIR / "screener_threshold.json"
    threshold = args.screen_threshold
    if threshold is None and saved.exists():
        threshold = json.loads(saved.read_text(encoding="utf-8"))["threshold"]  # chosen on the val split
    if threshold is not None:
        settings = settings.model_copy(update={"screen_threshold": threshold})
    verifier = _make_verifier(args.verifier, settings)
    detector = Detector()

    def build(camera: CameraConfig) -> Components:
        buffer = FrameBuffer()
        return Components(detector, make_trigger(settings, camera, buffer, blocking=True), verifier, buffer, camera)

    report: dict = {"meta": {}, "test": None, "demo": None}
    sources: list[str] = []
    clips: list[str] = []
    if args.set in ("test", "both"):
        files = _test_sources(settings, args.labels)
        if not files:
            print("test set: no labelled test-split sources (fill data/labels.csv); skipping")
        else:
            comp = build(BENCH_CAMERA)
            results = []
            for file, events in sorted(files.items()):
                print(f"  test {file}: {len(events)} event(s)")
                results.append(await run_source(DATASETS_DIR / file, events, comp, source_id=file))
            sources = sorted(files)
            report["test"] = {"aggregate": aggregate(results), "per_source": [r.model_dump() for r in results]}
    if args.set in ("demo", "both"):
        cams = load_cameras(settings.data_dir / "cameras.json")
        report["demo"] = await run_demo(cams, settings.data_dir, build)
        clips = [row["clip"] for row in report["demo"]["per_clip"]]
    report["meta"] = build_meta(settings, verifier, threshold, sources, clips)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_summary(report)
    print(f"wrote {out}")
    return 0


def print_summary(report: dict) -> None:
    meta = report["meta"]
    print(f"\ncommit {meta['commit'][:10]}  triggers={meta['triggers']}  verifier={meta['verifier']}")
    if meta["verifier"] == "mock":
        print("WARNING: mock verifier. These numbers are NOT valid evidence.")
    if report["test"]:
        a = report["test"]["aggregate"]
        print(f"TEST   events={a['events']}  recall step1={a['event_recall_step1']}  final={a['event_recall_final']}  "
              f"false/h final={a['false_per_hour_final']}  ai_filter={a['ai_filter_rate']}  "
              f"detect->card p50={a['detection_to_card_p50_s']}")
    if report["demo"]:
        for row in report["demo"]["per_clip"]:
            print(f"DEMO   {row['camera_id']} {row['clip']}: {row['outcome']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--set", choices=["test", "demo", "both"], default="both")
    ap.add_argument("--verifier", choices=["auto", "claude", "gemini", "mock"], default="auto")
    ap.add_argument("--triggers", choices=["rule", "llm", "both"], default=None, help="default: TRIGGERS from .env")
    ap.add_argument("--screen-threshold", type=float, default=None,
                    help="default: reports/screener_threshold.json if present, else SCREEN_THRESHOLD")
    ap.add_argument("--labels", type=Path, default=DATA_DIR / "labels.csv")
    ap.add_argument("--out", type=Path, default=REPORTS_DIR / "benchmark.json")
    return asyncio.run(amain(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
