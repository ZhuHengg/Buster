"""Grab 8 keyframes around a timestamp, call ClaudeVerifier once, print the JSON and latency.

Usage: uv run python scripts/verify_once.py data/case-2.mp4 6.4 [--camera CAM-02]
Needs ANTHROPIC_API_KEY (in backend/.env or the environment).
"""
import argparse
import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402

from app.config import DATA_DIR, Settings, load_cameras  # noqa: E402
from app.models import CandidateEvent  # noqa: E402
from app.verify.claude_verifier import ClaudeVerifier  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", type=Path)
    ap.add_argument("pts", type=float)
    ap.add_argument("--camera", default=None, help="camera id from cameras.json (default: the clip's camera)")
    args = ap.parse_args()

    settings = Settings()
    if not settings.anthropic_api_key:
        print("ANTHROPIC_API_KEY is not set")
        return 1
    cameras = load_cameras(DATA_DIR / "cameras.json")
    camera = next(
        (c for c in cameras if c.id == args.camera or (args.camera is None and c.clip == args.clip.name)),
        None,
    )
    if camera is None:
        print("no matching camera in cameras.json")
        return 1

    cap = cv2.VideoCapture(str(args.clip))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames: list[bytes] = []
    for i in range(8):
        t = max(0.0, args.pts - 3.0 + i * 6.0 / 7)
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, frame = cap.read()
        if ok:
            frames.append(cv2.imencode(".jpg", frame)[1].tobytes())
    cap.release()

    candidate = CandidateEvent(
        camera_id=camera.id, pts=args.pts, loop=0, trigger="rule", suspect_track_ids=[],
        detected_at=datetime.now(timezone.utc),
    )
    t0 = time.perf_counter()
    result = await ClaudeVerifier(settings).verify(candidate, frames, camera)
    print(result.model_dump_json(indent=2))
    print(f"latency: {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
