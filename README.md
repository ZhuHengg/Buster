# Proactive CCTV Alert System

Sime Darby Property University Hackathon 2026, Theme 1 (Safety and Security). Township CCTV clips play as live feeds. YOLO detection plus two Step 1 triggers (a rule-based one and a Gemini screener) look for a motorcycle snatch theft. Gemini (or Claude) verifies and describes the candidate. A guard approves or rejects it in the Central Monitoring System (CMS). Approval triggers a phone call and SMS.

- Design: [docs/SOLUTION_PLAN.md](docs/SOLUTION_PLAN.md), problem: [docs/PROBLEM_STATEMENT.md](docs/PROBLEM_STATEMENT.md)
- Phase 1 plan: [docs/superpowers/plans/2026-10-11-cctv-alert-phase1.md](docs/superpowers/plans/2026-10-11-cctv-alert-phase1.md)

## Read this first: what works and what does not (state at the end of Phase 1)

| Area | State |
|---|---|
| Backend (clip source, YOLO + ByteTrack + pose, Rule B, verifiers, incident lifecycle, escalation, REST + WebSocket, replay) | Built, 106 pytest tests pass |
| Frontend (camera grid with synced boxes, alert card, escalation timeline, incident log) | Built, 43 vitest tests pass, production build OK |
| Runs end to end with **zero credentials** (mock verifier + dry-run escalator) | Yes: verified in a headless browser |
| A clip with no snatch produces no alert | **Not tested.** There is no confirmed normal clip: `case-1.mp4` was first assumed normal, but it contains an on-foot snatch (see below). The old "0 alerts over 10 minutes" run was on that clip and means Rule B (motorcycle-only) ignores an on-foot snatch, not that it avoids false alarms. |
| **Rule B detects the snatch in `case-2.mp4`** | **No.** See "Rule B on the real footage". The snatch never becomes an alert from live detection. |
| Snatch to alert card within 10 s | **Not measurable**, because no alert is produced from the real clip |
| Real Claude verification | **Untested against the live API** (no `ANTHROPIC_API_KEY` was available). Tested with a fake client only. |
| Real Twilio call and SMS | **Untested against Twilio** (no credentials). Tested with a fake client only. |

The end-to-end alert path (card, approve, escalation timeline, reload mid-alert) was exercised by writing a pending incident straight into SQLite, because the detector never produces one from the clip. That proves the CMS and escalation half, not the detection half.

## Phase 2A: Gemini Step 1 screener (built, not yet run against the live API)

Plan: [docs/superpowers/plans/2026-10-11-cctv-alert-phase2-action-model.md](docs/superpowers/plans/2026-10-11-cctv-alert-phase2-action-model.md) (Part A). The VideoMAE training in Part B is deferred.

| Area | State |
|---|---|
| `GeminiScreener`, `GeminiTrigger`, `AnyTrigger`, `make_trigger` (Rule B + Gemini under one cooldown) | Built. Backend tests pass with a fake Gemini client only. |
| Live Gemini screening, latency, quota | **Run on the two demo clips only** (row below). Two bugs found and fixed on the way: the 8 s SDK deadline is below the API's 10 s minimum (every call failed with 400), and the trigger screened a one-frame buffer at the first frame. No quota or latency numbers yet. |
| Benchmark on the labelled dataset (`python -m training.bench_screener --split val|test`) | **Not run.** It needs the downloaded dataset in `backend/data/datasets/`, labelled with `training/ingest.py` (use `--whole-video-label snatch` for pre-trimmed clips) and `training/label_tool.py`, and a Gemini key. Results will be added here. |
| Both demo clips through the Gemini trigger (2026-10-12, default threshold 0.5, **not tuned**, `TRIGGERS=llm`, Gemini verifier, `scripts/benchmark.py --set demo`) | **`case-1` (on-foot snatch at about 12 to 16 s): detected.** Candidate at 14.3 s (2.3 s after the window start), Step 1 call 2.6 s, Gemini verification 3.7 s, plus 0.3 s push: about **8.9 s** to the alert card. One run, so this is one sample, not a median. It also raised 2 more candidates later in the clip (Step 2 removed one, one reached the guard); the window rule counts them as false, and I have not checked whether they are the chase or aftermath. **`case-2` (motorcycle snatch at about 5.4 to 8.4 s): missed.** Its only candidate was at 17.9 s, the aftermath (a bystander walks up to the victim on the ground), and Step 2 confirmed it. Gemini answers vary between runs. Do not tune the prompt or threshold on these clips: pick the threshold on the labelled val split with `training.bench_screener`. |

How it works: every `SCREEN_INTERVAL_S` of video time, while a person is in view, the last 3 s of the camera's frame buffer (6 JPEGs, 640 px wide, with YOLO boxes drawn) go to Gemini on a background thread. A score at or above `SCREEN_THRESHOLD` raises a candidate and the usual Step 2 verification follows. Rate-limit or API errors pause screening for 30 s and never stop the video loop.

Things to know:
- **Quota.** One analysed camera at the default interval is 20 Gemini calls a minute, plus one verification per candidate. Check your key's rate limits before analysing more than one camera or lowering the interval.
- **Benchmark protocol.** `--split val` picks the threshold and saves it with the model and prompt hash; `--split test` refuses to run if either changed, or if any screening call failed (failed calls are reported, never scored as negatives, and are retried on rerun because successful calls are cached). Each source's split is saved in `backend/reports/splits.json` so adding labels never moves a video between val and test. Commit that file.
- **No track IDs.** When Gemini sees a snatch that YOLO tracked poorly (the `case-2` situation), the incident has no snapshots and no tracker-based escape direction. The alert still reaches the guard.
- **Step 1 latency budget** is now up to 4 s (was 2 s) because of the Gemini round trip. The 10 s snatch to alert card target is unchanged and not yet measured.
- **Replay mode** (`MODE=replay`) never calls Gemini live: regenerate the replay files with `uv run python scripts/precompute.py CAM-02`, which uses `TRIGGERS` and needs the key.

## Phase 3: evidence, scale and the guard feedback loop (built; real-verifier numbers still to run)

Plan: [docs/superpowers/plans/2026-10-11-cctv-alert-phase3-evidence-scale.md](docs/superpowers/plans/2026-10-11-cctv-alert-phase3-evidence-scale.md).

| Area | State |
|---|---|
| `scripts/benchmark.py`: the real pipeline run offline over the **test split** of `labels.csv` and, separately, the demo clips, written to `backend/reports/benchmark.json` | Built and tested. Run once on the two demo clips with the mock verifier and Rule B (both missed: Rule B cannot see an on-foot snatch or the blurred motorcycle), and once with Gemini (row in Phase 2A: case-1 detected, case-2 missed). **No test-set run and no real-verifier run yet** (no labelled dataset, no API key here), so there are no recall or false-alarm numbers to quote. |
| `scripts/scale_test.py`: N simultaneous camera pipelines per fresh subprocess, stops at the first N that cannot keep up | Built, tested, **run on the real GPU** (below). |
| `/results` page in the CMS and `GET /api/reports` | Built, tested, checked in headless Chrome. Shows "baseline pending" until `backend/reports/baseline.json` is filled in, and a warning banner when the benchmark used the mock verifier. |
| `scripts/export_feedback.py`: guard-rejected alerts become `normal` rows in `labels.csv` (origin `feedback`) | Built and tested. No real incident has been rejected yet, so it has exported nothing. |
| Demo freeze: three dress rehearsals, replay mode with Wi-Fi off, final reports, tag `v1.0-demo` | **Not done.** They need the real verifier, Twilio and a person at the screen. No tag has been made. |

### Scale test result (RTX 3080 Laptop, `case-2.mp4`, 60 s per N, Rule B trigger, mock verifier)

| `--analyse-fps` | N = 1 | N = 2 | N = 4 | Cameras that keep up (mean fps >= 0.9 x target, p90 lag <= 1 s) |
|---|---|---|---|---|
| 10 | 9.1 fps | **7.2 fps, stop** | not run | **1** (`backend/reports/scale.json`, committed) |
| 5 | 4.9 fps | 4.9 fps | **4.0 fps, stop** | **2** |

The detector (YOLO11s detect + track and YOLO11s pose on a 938x1074 frame) costs about 94 ms per analysed frame, so one laptop GPU analyses roughly 15 frames per second in total. **Honest pitch line: one laptop-class GPU watches 1 camera at 10 fps or 2 cameras at 5 fps, so a township with N cameras needs about N GPUs at 10 fps (about N/2 at 5 fps), unless the detector is made faster** (smaller input size, batching frames across cameras, TensorRT) or the analysis moves to a server GPU. That has not been tried.

Lowest safe `ANALYSE_FPS` for Rule B: **10**. `case-2.mp4` cannot be used to time it (Rule B misses that clip), so this was checked on the synthetic snatch scene: at 10 fps both evidence paths (wrist reach, victim jerk) fire within 0.2 s of the full-rate result; below 10 fps the wrist-reach path starts missing its 0.5 s window, and the jerk path holds down to about 5 fps. A test pins the 10 fps behaviour.

### Commands

```powershell
cd backend
uv run python scripts/benchmark.py --set both --verifier gemini     # or claude; mock only for a smoke run
uv run python scripts/scale_test.py --clip data/case-2.mp4 --analyse-fps 10
uv run python scripts/export_feedback.py                            # guard-rejected incidents -> labels.csv
uv run python scripts/export_feedback.py --include-ai-rejected --confirm   # review each AI-rejected clip first
```

- **Benchmark rules.** Test-set sources come from the same saved split as the screener benchmark (`reports/splits.json`). The demo clips are reported in their own table and never mixed into test numbers. A mock-verifier run says so in `meta.verifier`, and the Results page shows a warning banner for it. The Gemini screener threshold is read from `reports/screener_threshold.json` (chosen on the val split) unless `--screen-threshold` is given. The expected snatch window of the demo clip is `expected_event` in `cameras.json` (CAM-02: 5.4 to 8.4 s, taken from the Phase 1 frame analysis; adjust if you re-label).
- **What a benchmark number means.** Step 1 candidates within 3 s of a labelled event count for it; candidates outside every event are false triggers, and ones Step 2 lets through are false alarms reaching the guard. If Step 2 is unavailable the alert still reaches the guard, so it counts as confirmed (and `verify_errors` counts them). Detection latency is video time from the event start plus the wall time of the Step 1 call, verification is wall time, and the UI push is a constant 0.3 s.
- **`backend/reports/baseline.json`** is filled by hand from the guard interviews (`{"time_to_notice_s": 90, "source": "guard interviews, n=5"}`). Null or non-numeric values show "baseline pending". Nothing in the code invents a baseline.
- **Feedback loop.** `export_feedback.py` only appends, skips incidents already exported (`fb_<incident id>`), copies each clip segment under `data/datasets/feedback/`, and refuses incidents from the demo clips. An AI-rejected incident is exported only after a person confirms it was normal; ones marked "real snatch" are listed for hand labelling. After exporting, rebuild the dataset and re-benchmark.

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
| `GEMINI_API_KEY` | Enables the Gemini verifier (takes priority over Claude). Untested against the live API; fake client only. |
| `GEMINI_MODEL` | Default `gemini-2.5-flash`. JSON-schema structured output, thinking budget 0. |
| `GEMINI_SCREEN_MODEL` | Model for the Step 1 screener. Empty: same as `GEMINI_MODEL` (a `-lite` model is cheaper). |
| `TRIGGERS` | `rule`, `llm` or `both` (default `both`). Without `GEMINI_API_KEY` it is always Rule B only. |
| `SCREEN_THRESHOLD`, `SCREEN_INTERVAL_S` | Screener score needed to raise a candidate (default 0.5; set it to the value in `backend/reports/screener_threshold.json` after the benchmark) and seconds between screenings per camera (default 3.0). |
| `ANTHROPIC_API_KEY` | Enables the Claude verifier when no Gemini key is set. Neither key set: the mock verifier is used. |
| `CLAUDE_MODEL` | Default `claude-opus-5-5`. Requested with effort `low`, structured output, and server-side refusal fallback. |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `POLICE_NUMBER` | All four set: real call and SMS. Otherwise the dry-run escalator simulates them. |
| `GATE_NUMBER` | Gate guard SMS. Missing: that step shows as skipped. |
| `MODE` | `live` (default) or `replay` |
| `OPERATOR_NAME` | Backend default for the operator on a decision. The CMS sends its own (see below). |
| `ANALYSE_FPS` | Detect at most this many frames per second per camera (default: every frame). Skipped frames are still buffered for keyframes. 10 is the lowest safe value for Rule B. |
| `DB_PATH`, `DATA_DIR`, `REPORTS_DIR` | Override the incident database, the clip folder and the folder `/api/reports` reads |

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

Current assignment: `case-2.mp4` on CAM-02 (the snatch) and `case-1.mp4` on CAM-07 (an on-foot bag snatch at about 12 to 16 s, no motorcycle: a man in black runs up behind a woman, grabs her bag, she falls, he runs off). The other seven tiles have no clip yet. Neither demo clip is a normal clip.

### TODO-USER (not answered in the request, so assumed)

- The request left the clip labels and the escape direction as blank template brackets. The assignment above was **inferred from the footage**: `case-2.mp4` shows a bag snatch (victim falls, bike flees toward the image right), `case-1.mp4` was first read as an ordinary street, and the user corrected that on 2026-10-12: it is a snatch too. The snatch window in `cameras.json` (CAM-07: 12 to 16 s, CAM-02: 5.4 to 8.4 s) is from watching the clips; please confirm the times.
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

- `case-1.mp4` (an on-foot snatch at about 12 to 16 s): 0 events. Expected: Rule B needs a motorcycle in contact, so it cannot see a snatch by a person on foot. The Gemini screener has no such limit.
- `case-2.mp4` (snatch): **0 events.** The motorcycle is small, motion-blurred and heavily compressed (a news re-encode). YOLO11 s, m and x (imgsz 640 and 1280) see it in only 13 to 18 of the 91 frames around the snatch (5.4 to 8.4 s), and almost never after the grab, so no stable motorcycle track forms. Lowering the motorcycle confidence to 0.05, a lower-threshold ByteTrack config, `min_track_frames` 2 to 3 and `proximity_ratio` up to 2.2 did not produce a contact, grab, getaway chain.
- At very low confidence the bike's path is visible (it leaves toward the image right and slightly up), so a detector trained on this footage, or the Phase 2 VideoMAE trigger, should close the gap. The `Trigger` protocol in `backend/app/trigger/base.py` is where it plugs in. The rule logic itself is covered by synthetic-scene tests (contact, grab by wrist or jerk, getaway, cooldown, loop wrap).

Final `SnatchParams` are the plan defaults: `window_s=3.0`, `proximity_ratio=1.0`, `reach_ratio=0.35`, `jerk_ratio=0.25`, `accel_ratio=1.5`, `cooldown_s=10.0`, `min_track_frames=5`.

## Measured results

| Check | Result |
|---|---|
| Backend tests | 246 passed (Phase 1: 106, Phase 2A: 196) |
| Frontend tests | 54 passed, production build OK |
| Snatch to alert card (spec: 10 s or less), 3 runs | Not measurable: no alert is produced from the snatch clip (see above). Pipeline stage timings are recorded per incident (`metrics`: `candidate_s`, `verified_s`, `shown_s`, `call_placed_s`, seconds since detection) and shown on the Incidents page. |
| Approval to phone ringing (spec: 5 s or less) | Dry-run escalator: ringing is emitted 0.5 s after approval. Real Twilio timing not measured. |
| Live run, 10 min 23 s (about 10 loops of `case-1.mp4`, both cameras analysed, Rule B only) | 0 incidents and 0 pipeline errors, so the pipeline is stable. **This is not a false-alarm result:** `case-1.mp4` contains a snatch (on foot), which Rule B cannot see. There is still no run on genuinely normal footage. |
| Replay mode vs live | Same message types and fields (`camera.sync`, `detections`, `incident.updated`). Replay emits every frame (about 30 per second per camera), live about 9 to 14. Precomputed: CAM-07 1776 frames, CAM-02 833 frames, 0 candidates each. |

## Known issues

- **Rule B misses the snatch in `case-2.mp4`** (see above), so with `TRIGGERS=rule` the snatch never becomes an alert from live detection. The Gemini screener is the intended fix and has not run against the live API.
- **No real-verifier, real-Gemini or real-Twilio run** has happened. Benchmarks and timings that depend on them are unmeasured: snatch to alert card (10 s target) and approval to ringing (5 s target).
- **The benchmark has never run on a labelled test split**, so the Results page KPI tiles show a dash for recall and false alarms until a dataset is labelled and a real-verifier benchmark is run.
- **Throughput is 1 camera per laptop GPU at 10 fps** (Phase 3 scale test).
- **Three dress rehearsals and the Wi-Fi-off replay rehearsal have not been done**, and nothing is tagged `v1.0-demo`.
- The scale test measures Rule B plus the dry-run verifier. A run with the Gemini trigger adds network calls (quota) but no GPU load.

## Pre-stage checklist

1. Phone on a hotspot (the demo needs no internet except Claude and Twilio) and the laptop on power.
2. Twilio: verify the destination numbers (trial accounts can only call verified numbers), enable **Malaysia** under Voice Geo permissions, and set `TWILIO_*`, `POLICE_NUMBER`, `GATE_NUMBER`. Place one test call before going on stage.
3. `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`) set, and run `uv run python scripts/verify_once.py data/case-2.mp4 6.4` once (expect `is_incident: true`, latency 6 s or less).
4. Replay files are fresh (`scripts/precompute.py` for every analysed camera) if you plan to run `MODE=replay`.
5. Browser volume on, and click the page once so the browser allows the alert tone to play.
6. Clear old demo incidents: stop the backend and delete `backend/data/incidents.db` and `backend/data/snapshots/`.
7. `backend/reports/baseline.json` filled from the guard interviews, and `/results` opened once to check it shows real numbers (no mock banner).
8. Rehearse: reload the page mid-alert (the card must come back), click Approve twice (second is "Already handled").

## Rules the system enforces

- Nothing escalates without guard approval. The escalators refuse any incident not in status `APPROVED`, and approving twice or after a reject returns 409.
- No face recognition and no identity lookup. Snapshots are plain image crops stored per incident and deleted when the guard rejects it (or the AI rejects it).
- If Claude is down, slow (12 s timeout) or refuses, the candidate still reaches the guard as an unverified alert ("AI verification unavailable: operator to confirm").
