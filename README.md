# Proactive CCTV Alert System

Phase 1 demo. Design: `docs/SOLUTION_PLAN.md`. Plan: `docs/superpowers/plans/2026-10-11-cctv-alert-phase1.md`.
Full runbook is written in Task 14.

## Clip probe (`uv run python scripts/probe_clips.py`)

```
case-1.mp4: 30.00 fps, 1194x618, 59.2 s, codec=h264, h264=True
case-2.mp4: 30.00 fps, 938x1074, 27.8 s, codec=h264, h264=True
```

Both clips are already H.264, so no transcode needed.

## TODO-USER

- Which clip shows the snatch, and which is the normal clip: not yet provided. Both are `analyse: true` (case-1 on CAM-07, case-2 on CAM-02).
- `exits` and `compass` in `backend/data/cameras.json` are placeholders (`up` -> `Gate B`, compass up=north, down=south, left=west, right=east). Replace with the real escape direction and gate for the snatch camera.

## Rule B tuning on the real clips (Task 5, step 5)

Inferred from the footage (not yet confirmed by the user): `case-2.mp4` is the snatch, `case-1.mp4` is the normal clip.

- `case-2.mp4` (snatch, 938x1074, news-style re-encode): bike enters from the left at about 5.6 s, grab at about 6.2 to 6.8 s, victim falls, bike escapes toward the right/up-right of the frame (image direction `right`).
- `case-1.mp4` (normal street, parked motorcycles, people walking and running): `scripts/debug_rule.py` reports 0 events with the default `SnatchParams`. Contact flags appear near the parked bikes, never a getaway.
- **Rule B does not fire on `case-2.mp4`.** Stock YOLO11 (s/m/x, imgsz 640/1280) sees the motorcycle in only 13 to 18 of 91 frames around the snatch, and almost nothing after the grab (motion blur, compression, small target). Lowering the moto confidence to 0.05, a lower-threshold ByteTrack config, `min_track_frames` 2 to 3 and `proximity_ratio` up to 2.2 did not yield a stable moto track, so no contact/grab/getaway chain forms. The rule logic itself is verified by the synthetic-scene unit tests.
- Final `SnatchParams` defaults are therefore the plan's defaults. Closing this gap is the job of the Phase 2 model-based Trigger (or a motorcycle detector trained on this footage).
