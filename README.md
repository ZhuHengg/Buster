# Proactive CCTV Alert System

Sime Darby Property University Hackathon 2026, Theme 1 (Safety and Security). Township CCTV clips play as live feeds. YOLO detection plus a rule-based trigger looks for a motorcycle snatch theft. Claude verifies and describes the candidate. A guard approves or rejects it in the Central Monitoring System (CMS). Approval triggers a phone call and SMS.

- Design: [docs/SOLUTION_PLAN.md](docs/SOLUTION_PLAN.md), problem: [docs/PROBLEM_STATEMENT.md](docs/PROBLEM_STATEMENT.md)
- Phase 1 plan: [docs/superpowers/plans/2026-10-11-cctv-alert-phase1.md](docs/superpowers/plans/2026-10-11-cctv-alert-phase1.md)

## Read this first: what works and what does not (state at the end of Phase 1)

| Area | State |
|---|---|
| Backend (clip source, YOLO + ByteTrack + pose, Rule B, verifiers, incident lifecycle, escalation, REST + WebSocket, replay) | Built, 106 pytest tests pass |
| Frontend (camera grid with synced boxes, alert card, escalation timeline, incident log) | Built, 43 vitest tests pass, production build OK |
| Runs end to end with **zero credentials** (mock verifier + dry-run escalator) | Yes: verified in a headless browser |
| Normal clip produces no alert | Yes (0 events from `debug_rule.py`, and 0 incidents over the 10 minute live run below) |
| **Rule B detects the snatch in `case-2.mp4`** | **No.** See "Rule B on the real footage". The snatch never becomes an alert from live detection. |
| Snatch to alert card within 10 s | **Not measurable**, because no alert is produced from the real clip |
| Real Claude verification | **Untested against the live API** (no `ANTHROPIC_API_KEY` was available). Tested with a fake client only. |
| Real Twilio call and SMS | **Untested against Twilio** (no credentials). Tested with a fake client only. |

The end-to-end alert path (card, approve, escalation timeline, reload mid-alert) was exercised by writing a pending incident straight into SQLite, because the detector never produces one from the clip. That proves the CMS and escalation half, not the detection half.

## Setup

Windows 11, NVIDIA GPU (developed on an RTX 3080 Laptop, 16 GB). The system `python` is 3.14 and must not be used: the PyTorch CUDA wheels target Python 3.12, which uv installs for you.

```powershell
# backend
cd backend
uv sync --python 3.12            # installs torch from the cu128 index
uv run python -c "import torch; print(torch.cuda.is_available())"   # expect True
copy .env.example .env           # all values optional

# frontend
cd ..\frontend
npm install
copy .env.local.example .env.local
```

Ultralytics downloads `yolo11s.pt` and `yolo11s-pose.pt` into `backend/` on first use (needs internet once; `*.pt` is git-ignored).

## Run

```powershell
# terminal 1
cd backend
uv run uvicorn app.main:app --port 8000

# terminal 2
cd frontend
npm run dev            # or: npm run build; npm start    (http://localhost:3000)
```

Tests: `cd backend; uv run pytest` and `cd frontend; npx vitest run`. The one GPU test is marked `gpu` and skips itself without CUDA.

### Environment variables (`backend/.env`, all optional)

| Variable | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Enables the Claude verifier. Missing: the mock verifier is used. |
| `CLAUDE_MODEL` | Default `claude-opus-5-5`. Requested with effort `low`, structured output, and server-side refusal fallback. |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `POLICE_NUMBER` | All four set: real call and SMS. Otherwise the dry-run escalator simulates them. |
| `GATE_NUMBER` | Gate guard SMS. Missing: that step shows as skipped. |
| `MODE` | `live` (default) or `replay` |
| `OPERATOR_NAME` | Backend default for the operator on a decision. The CMS sends its own (see below). |
| `DB_PATH`, `DATA_DIR` | Override the incident database and clip folder |

Frontend (`frontend/.env.local`): `NEXT_PUBLIC_API_BASE` (default `http://localhost:8000`), `NEXT_PUBLIC_OPERATOR_NAME` (shown in the header and sent with Approve/Reject), `NEXT_PUBLIC_TOWNSHIP_NAME`.

## Clips and cameras

Clips live in `backend/data/` and are served with HTTP Range support. Browsers only play H.264, so check new clips:

```powershell
cd backend
uv run python scripts/probe_clips.py              # fps, size, duration, codec
uv run python scripts/probe_clips.py --transcode  # re-encode non-H.264 clips with the bundled ffmpeg
```

Probe output for the current clips (both are already H.264):

```
case-1.mp4: 30.00 fps, 1194x618, 59.2 s, codec=h264, h264=True
case-2.mp4: 30.00 fps, 938x1074, 27.8 s, codec=h264, h264=True
```

`backend/data/cameras.json` is a list of 9 cameras (3x3 grid):

```json
{ "id": "CAM-02", "name": "Elmina Shoplot Row B", "location": "Elmina Central, Row B",
  "clip": "case-2.mp4", "analyse": true,
  "exits": { "right": "Gate B" },
  "compass": { "up": "north", "down": "south", "left": "west", "right": "east" } }
```

- `clip: null` renders a "SIGNAL LOST" tile. `analyse: true` runs the pipeline on that clip and requires the file to exist.
- `exits` maps the image direction the motorcycle leaves toward to a gate name, `compass` maps it to a compass word. Both feed the alert card, the call script and the SMS.
- Add footage by copying an H.264 `.mp4` into `backend/data/` and pointing a camera at it. Restart the backend.

Current assignment: `case-2.mp4` on CAM-02 (the snatch) and `case-1.mp4` on CAM-07 (normal street). The other seven tiles have no clip yet.

### TODO-USER (not answered in the request, so assumed)

- The request left the clip labels and the escape direction as blank template brackets. The assignment above was **inferred from the footage**: `case-2.mp4` shows a bag snatch (victim falls, bike flees toward the image right), `case-1.mp4` shows an ordinary street with parked motorcycles. Please confirm.
- Gate name for the escape direction: `Gate B` is a placeholder in `cameras.json` (right of the image is the observed direction). Replace it with the real gate.
- `data/mock_verifications/CAM-02.json` (the no-key verification text) was written from watching the clip, not from a model.

## Live and replay mode

- **Live** (`MODE=live`): each analysed camera runs clip, YOLO + ByteTrack + pose, Rule B, then Claude (or mock) verification. The pipeline drops frames when it cannot keep up, so detection timestamps stay on the wall clock and the overlay stays aligned with the video. With two cameras on one laptop GPU it processes roughly 9 to 14 frames per second per camera.
- **Replay** (`MODE=replay`): plays precomputed output with the same WebSocket messages and timing, with no GPU work. Generate the files first:

```powershell
cd backend
uv run python scripts/precompute.py CAM-02     # writes data/precomputed/CAM-02.json (+ snapshots)
uv run python scripts/precompute.py CAM-07
$env:MODE="replay"; uv run uvicorn app.main:app --port 8000
```

Replay re-injects each precomputed candidate once per clip loop and shows its stored verification about 2 s later, to mimic the Claude latency.

## Rule B on the real footage

`backend/scripts/debug_rule.py data/<clip>.mp4` runs the detector and rule offline and prints each event plus per-second contact, grab and getaway flags. Result with the plan's default `SnatchParams`:

- `case-1.mp4` (normal): 0 events. Contact flags appear near the parked bikes, never a getaway.
- `case-2.mp4` (snatch): **0 events.** The motorcycle is small, motion-blurred and heavily compressed (a news re-encode). YOLO11 s, m and x (imgsz 640 and 1280) see it in only 13 to 18 of the 91 frames around the snatch (5.4 to 8.4 s), and almost never after the grab, so no stable motorcycle track forms. Lowering the motorcycle confidence to 0.05, a lower-threshold ByteTrack config, `min_track_frames` 2 to 3 and `proximity_ratio` up to 2.2 did not produce a contact, grab, getaway chain.
- At very low confidence the bike's path is visible (it leaves toward the image right and slightly up), so a detector trained on this footage, or the Phase 2 VideoMAE trigger, should close the gap. The `Trigger` protocol in `backend/app/trigger/base.py` is where it plugs in. The rule logic itself is covered by synthetic-scene tests (contact, grab by wrist or jerk, getaway, cooldown, loop wrap).

Final `SnatchParams` are the plan defaults: `window_s=3.0`, `proximity_ratio=1.0`, `reach_ratio=0.35`, `jerk_ratio=0.25`, `accel_ratio=1.5`, `cooldown_s=10.0`, `min_track_frames=5`.

## Measured results

| Check | Result |
|---|---|
| Backend tests | 106 passed |
| Frontend tests | 43 passed |
| Snatch to alert card (spec: 10 s or less), 3 runs | Not measurable: no alert is produced from the snatch clip (see above). Pipeline stage timings are recorded per incident (`metrics`: `candidate_s`, `verified_s`, `shown_s`, `call_placed_s`, seconds since detection) and shown on the Incidents page. |
| Approval to phone ringing (spec: 5 s or less) | Dry-run escalator: ringing is emitted 0.5 s after approval. Real Twilio timing not measured. |
| False alarms on the normal clip, live mode, 10 min 23 s (about 10 loops of `case-1.mp4`, both cameras analysed) | 0 incidents of any status (0 PENDING_REVIEW, 0 AI_REJECTED, 0 CANDIDATE), 0 pipeline errors. Caveat: the rule also produces nothing on the snatch clip, so this is a negative control, not evidence of discrimination. |
| Replay mode vs live | Same message types and fields (`camera.sync`, `detections`, `incident.updated`). Replay emits every frame (about 30 per second per camera), live about 9 to 14. Precomputed: CAM-07 1776 frames, CAM-02 833 frames, 0 candidates each. |

## Pre-stage checklist

1. Phone on a hotspot (the demo needs no internet except Claude and Twilio) and the laptop on power.
2. Twilio: verify the destination numbers (trial accounts can only call verified numbers), enable **Malaysia** under Voice Geo permissions, and set `TWILIO_*`, `POLICE_NUMBER`, `GATE_NUMBER`. Place one test call before going on stage.
3. `ANTHROPIC_API_KEY` set, and run `uv run python scripts/verify_once.py data/case-2.mp4 6.4` once (expect `is_incident: true`, latency 6 s or less).
4. Replay files are fresh (`scripts/precompute.py` for every analysed camera) if you plan to run `MODE=replay`.
5. Browser volume on, and click the page once so the browser allows the alert tone to play.
6. Clear old demo incidents: stop the backend and delete `backend/data/incidents.db` and `backend/data/snapshots/`.
7. Rehearse: reload the page mid-alert (the card must come back), click Approve twice (second is "Already handled").

## Rules the system enforces

- Nothing escalates without guard approval. The escalators refuse any incident not in status `APPROVED`, and approving twice or after a reject returns 409.
- No face recognition and no identity lookup. Snapshots are plain image crops stored per incident and deleted when the guard rejects it (or the AI rejects it).
- If Claude is down, slow (12 s timeout) or refuses, the candidate still reaches the guard as an unverified alert ("AI verification unavailable: operator to confirm").
