"""Run the pipeline offline on a camera's clip and write data/precomputed/<camera_id>.json.

The file feeds ReplayPipeline (MODE=replay), which plays it back with the same WebSocket
messages and timing as the live pipeline. Snapshots go next to it as <camera_id>_<track_id>.jpg.

Usage: uv run python scripts/precompute.py CAM-02 [--loops 1]
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR, Settings, load_cameras  # noqa: E402
from app.detect.detector import Detector  # noqa: E402
from app.models import CandidateEvent  # noqa: E402
from app.trigger.direction import escape_direction  # noqa: E402
from app.trigger import make_trigger  # noqa: E402
from app.verify.base import VerificationUnavailable  # noqa: E402
from app.verify.mock_verifier import make_verifier  # noqa: E402
from app.video.buffer import FrameBuffer  # noqa: E402
from app.video.source import ClipSource  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("camera_id")
    ap.add_argument("--loops", type=int, default=1, help="how many passes over the clip to analyse")
    args = ap.parse_args()

    settings = Settings()
    camera = next((c for c in load_cameras(settings.data_dir / "cameras.json") if c.id == args.camera_id), None)
    if camera is None or not camera.clip:
        print(f"unknown or clip-less camera: {args.camera_id}")
        return 1

    source = ClipSource(settings.data_dir / camera.clip, realtime=False)
    detector, buffer, verifier = Detector(), FrameBuffer(), make_verifier(settings)
    trigger = make_trigger(settings, camera, buffer, blocking=True)  # offline: video time outruns wall time
    out_dir = settings.data_dir / "precomputed"
    out_dir.mkdir(parents=True, exist_ok=True)

    frames: list[dict] = []
    candidates: list[dict] = []
    recent = []
    for frame, pts, loop in source:
        if loop >= args.loops:
            break
        fd = detector.process(frame, camera.id, pts, loop)
        buffer.push(pts, loop, frame, fd)
        recent.append(fd)
        frames.append(fd.model_dump(mode="json", exclude={"tracks": {"__all__": {"keypoints"}}}))
        event: CandidateEvent | None = trigger.update(fd)
        if event is None:
            continue
        for track_id in event.suspect_track_ids:
            snap = buffer.best_snapshot(track_id)
            if snap is not None:
                (out_dir / f"{camera.id}_{track_id}.jpg").write_bytes(snap)
        direction = (None, None)
        if event.motorcycle_track_id is not None:
            direction = escape_direction(recent, event.motorcycle_track_id, camera)
        try:
            verification = await verifier.verify(event, buffer.keyframes(event.pts), camera)
        except VerificationUnavailable as exc:
            print(f"  verification unavailable: {exc}")
            verification = None
        candidates.append(
            {
                "candidate": event.model_dump(mode="json"),
                "verification": verification.model_dump(mode="json") if verification else None,
                "direction": list(direction),
            }
        )
        print(f"  candidate at pts={event.pts:.2f} (loop {event.loop})")

    path = out_dir / f"{camera.id}.json"
    payload = {"fps": source.fps, "frames": frames, "candidates": candidates}
    path.write_text(json.dumps(payload), encoding="utf-8")
    print(f"{camera.id}: {len(frames)} frames, {len(candidates)} candidate(s) -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
