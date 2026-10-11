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
