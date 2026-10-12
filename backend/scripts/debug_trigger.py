"""Run the real detector and trigger(s) over a clip and print each candidate with its delay.

Usage: uv run python scripts/debug_trigger.py data/case-2.mp4 --triggers llm --snatch-at 6.4
       uv run python scripts/debug_trigger.py data/case-1.mp4 --triggers both

The Gemini threshold is read from reports/screener_threshold.json when present (written by
`python -m training.bench_screener --split val`). Do not tune the prompt or threshold on demo clips.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BACKEND_DIR, DATA_DIR, Settings, load_cameras  # noqa: E402
from app.detect.detector import Detector  # noqa: E402
from app.trigger import make_trigger  # noqa: E402
from app.video.buffer import FrameBuffer  # noqa: E402
from app.video.source import ClipSource  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", type=Path)
    ap.add_argument("--camera", default=None, help="camera id (default: the camera whose clip this is)")
    ap.add_argument("--triggers", choices=["rule", "llm", "both"], default="both")
    ap.add_argument("--snatch-at", type=float, default=None, help="labelled snatch time in seconds")
    args = ap.parse_args()

    settings = Settings().model_copy(update={"triggers": args.triggers})
    threshold_file = BACKEND_DIR / "reports" / "screener_threshold.json"
    if threshold_file.exists():
        threshold = json.loads(threshold_file.read_text(encoding="utf-8"))["threshold"]
        settings = settings.model_copy(update={"screen_threshold": threshold})
        print(f"screen_threshold = {threshold:.3f} (from {threshold_file.name})")
    else:
        print(f"screen_threshold = {settings.screen_threshold} (default; no benchmark threshold saved)")

    cameras = load_cameras(DATA_DIR / "cameras.json")
    camera = next(
        (c for c in cameras if c.id == args.camera or (args.camera is None and c.clip == args.clip.name)), None
    )
    if camera is None:
        print("no matching camera in cameras.json")
        return 1

    buffer = FrameBuffer()
    trigger = make_trigger(settings, camera, buffer, blocking=True)
    detector = Detector()
    found = 0
    for frame, pts, loop in ClipSource(args.clip, realtime=False):
        if loop > 0:
            break
        fd = detector.process(frame, camera.id, pts, loop)
        buffer.push(pts, loop, frame, fd)
        event = trigger.update(fd)
        if event is None:
            continue
        found += 1
        delay = "" if args.snatch_at is None else f", {event.pts - args.snatch_at:+.1f} s from the labelled snatch"
        print(f"candidate: trigger={event.trigger} pts={event.pts:.2f}{delay} "
              f"suspects={event.suspect_track_ids} moto={event.motorcycle_track_id}")
    print(f"{found} candidate(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
