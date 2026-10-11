"""Run Detector + SnatchRule over a clip (not real time) and print events and per-second flags.

Usage: uv run python scripts/debug_rule.py data/case-1.mp4 [--loops 1]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.detect.detector import Detector  # noqa: E402
from app.trigger.snatch_rule import SnatchRule  # noqa: E402
from app.video.source import ClipSource  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", type=Path)
    ap.add_argument("--loops", type=int, default=1)
    args = ap.parse_args()

    source = ClipSource(args.clip, realtime=False)
    detector, rule = Detector(), SnatchRule()
    second_flags: dict[int, dict[str, bool]] = {}
    n_motos = n_persons = 0
    events = []
    for frame, pts, loop in source:
        if loop >= args.loops:
            break
        fd = detector.process(frame, args.clip.stem, pts, loop)
        n_motos += sum(t.cls == "motorcycle" for t in fd.tracks)
        n_persons += sum(t.cls == "person" for t in fd.tracks)
        ev = rule.update(fd)
        flags = second_flags.setdefault(int(pts), {"contact": False, "grab": False, "getaway": False})
        for k, v in rule.diagnostics.items():
            flags[k] = flags[k] or v
        if ev:
            events.append(ev)
            print(f"EVENT pts={ev.pts:.2f} loop={ev.loop} victim={ev.victim_track_id} "
                  f"moto={ev.motorcycle_track_id} suspects={ev.suspect_track_ids}")
    print(f"{args.clip.name}: {len(events)} event(s); person-detections={n_persons}, moto-detections={n_motos}")
    for sec in sorted(second_flags):
        f = second_flags[sec]
        print(f"  t={sec:3d}s  contact={int(f['contact'])} grab={int(f['grab'])} getaway={int(f['getaway'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
