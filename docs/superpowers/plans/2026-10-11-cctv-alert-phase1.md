# Proactive CCTV Alert System: Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimum complete demo. CCTV clips play as live feeds. YOLO detection plus a rule-based trigger finds a motorcycle snatch theft. Claude verifies and describes it. A guard approves or rejects it in a Next.js Central Monitoring System (CMS), and approval triggers a phone call and SMS.

**Architecture:** A Python FastAPI backend runs one pipeline per analysed camera: clip source → YOLO + ByteTrack (+ pose) → rule trigger (Step 1) → Claude verification (Step 2) → incident store (SQLite) → escalation (Twilio) after guard approval. It pushes detections and incident events over one WebSocket. A Next.js frontend plays the same clip files in `<video>` tiles and draws boxes on a `<canvas>` overlay, matched by playback timestamp. A replay mode plays precomputed pipeline output instead of live inference, with an identical WebSocket output.

**Tech Stack:** Python 3.12, uv, FastAPI, Uvicorn, Ultralytics YOLO (detect + pose, ByteTrack), OpenCV, PyTorch CUDA (cu128 wheels), Anthropic Python SDK, Twilio Python SDK, SQLite (stdlib `sqlite3`), pytest. Next.js (App Router) + TypeScript + Tailwind CSS, Vitest.

**Spec:** `docs/SOLUTION_PLAN.md` (design) and `docs/PROBLEM_STATEMENT.md` (context). Read both before starting.

**Out of this plan (Phase 2, separate plan later):** training the VideoMAE action model (spec §6.3 A, §7). Phase 1 uses Rule B only as the Step 1 trigger. Leave a `Trigger` interface so the model can be added later.

## Global Constraints

- Python **3.12** via uv (`uv sync --python 3.12`). The machine's default `python` is 3.14; do not use it, because PyTorch CUDA wheels target 3.12.
- PyTorch from the `https://download.pytorch.org/whl/cu128` index (explicit uv index for `torch`, `torchvision`). GPU: RTX 3080 Laptop, 16 GB. OS: Windows 11; use `pathlib` for all paths.
- Backend runs on `http://localhost:8000`, frontend on `http://localhost:3000`. Allow CORS for the frontend origin.
- Clips live in `backend/data/` (currently `case-1.mp4`, `case-2.mp4`). `backend/data/` is git-ignored except `cameras.json` and `.gitkeep`.
- **No face recognition, no face embeddings, no identity lookup.** Snapshots are image crops only, stored per incident, and deleted when the guard rejects the incident.
- **Nothing escalates without guard approval.** Escalation code paths must refuse any incident whose status is not `APPROVED`.
- Step 2 model ID comes from the env var `CLAUDE_MODEL`, default `claude-opus-5-5`, with effort `low` and structured outputs. Before writing the verifier, **read the `claude-api` skill** (Python README) for the exact SDK calls (structured outputs via `output_config.format` / `messages.parse`, `fallbacks: "default"` with beta `server-side-fallback-2026-07-01`, refusal `stop_reason` handling).
- Every external service is optional. If `ANTHROPIC_API_KEY` is missing, use the mock verifier; if the Twilio variables are missing, use the dry-run escalator. The app must run end to end with **zero** credentials.
- Browsers only play H.264 MP4. Task 1's probe script reports each clip's codec. If a clip is not H.264, transcode it with the `imageio-ffmpeg` bundled binary (ffmpeg is not installed system-wide).
- Incident replay uses the **original clip plus start and end times**. Do not encode new video files (OpenCV's Windows wheels cannot reliably write H.264).
- Timing targets (spec §8): snatch → alert card ≤ 10 s; approval → phone ringing ≤ 5 s; 0 alerts on normal clips.
- UI copy and look: dark control-room theme; camera labels like `CAM-07 · Elmina Shoplot Row B`; monospaced timestamps; no debug text visible in the CMS.

## Review Focus

1. **Clip loop wrap-around:** when a clip loops, the timestamp (pts) jumps back to 0 and track IDs restart. The rule must reset and never fire on the jump, and the frontend overlay must not show stale boxes. Test in Task 5, Task 9 and Task 10; checked manually in Task 11.
2. **Duplicate triggers for one event:** a snatch spans many frames, so the rule may fire repeatedly. Exactly one incident per event (cooldown per camera). Test in Task 5.
3. **Verifier failure or timeout:** if Claude is down, slow or refuses, the candidate must still reach the guard as `PENDING_REVIEW` with "AI verification unavailable". Missing an alert is worse than an unverified one. Test in Task 6, Task 7 and Task 9.
4. **Double or conflicting guard actions:** Approve clicked twice, or Approve after Reject, returns 409 and escalates at most once. Test in Task 7, Task 9 and Task 12.
5. **Frontend reconnect or refresh mid-incident:** after a WebSocket drop or a page reload, pending incidents reappear (loaded from REST) and the alert card is not lost. Test in Task 10; checked manually in Task 12.

---

## File Structure

```
backend/
  pyproject.toml                 uv project (deps above), pytest config
  .env.example                   ANTHROPIC_API_KEY, CLAUDE_MODEL, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
                                 TWILIO_FROM_NUMBER, POLICE_NUMBER, GATE_NUMBER, MODE=live|replay, OPERATOR_NAME
  data/cameras.json              camera config (see Task 1)
  app/config.py                  Settings (pydantic-settings) + load_cameras()
  app/models.py                  all pydantic domain models + status transitions
  app/video/source.py            ClipSource (real-time paced, looping)
  app/video/buffer.py            FrameBuffer ring buffer, keyframes, snapshot picking
  app/detect/detector.py         Detector (YOLO track + pose merge)
  app/trigger/base.py            Trigger protocol
  app/trigger/snatch_rule.py     SnatchRule (Rule B)
  app/trigger/direction.py       escape direction from tracks
  app/verify/base.py             Verifier protocol
  app/verify/claude_verifier.py  ClaudeVerifier
  app/verify/mock_verifier.py    MockVerifier
  app/incidents/store.py         SQLite IncidentStore
  app/incidents/service.py       IncidentService (lifecycle, metrics)
  app/escalation/script.py       call/SMS text builders
  app/escalation/escalator.py    TwilioEscalator, DryRunEscalator
  app/pipeline.py                CameraPipeline + replay player
  app/ws.py                      WebSocket hub
  app/main.py                    FastAPI app, routes, startup
  scripts/probe_clips.py         print fps/resolution/duration/codec of clips
  scripts/precompute.py          run pipeline offline → data/precomputed/<camera_id>.json
  tests/...                      mirrors app/
frontend/
  (create-next-app, TypeScript, Tailwind, App Router, src/ dir)
  src/lib/types.ts               TS mirrors of backend models
  src/lib/api.ts                 REST client
  src/lib/ws.ts                  useCmsSocket hook + reducer
  src/lib/overlay.ts             bbox → canvas mapping, nearest-detection lookup
  src/components/CameraGrid.tsx, CameraTile.tsx, AlertCard.tsx, EscalationTimeline.tsx, IncidentTable.tsx
  src/app/page.tsx               CMS dashboard
  src/app/incidents/page.tsx     incident log + detail
  public/sounds/alert.mp3        alert tone (any royalty-free short tone)
README.md                        setup + demo runbook
```

---

### Task 1: Backend scaffold, settings, camera config, clip probe

**Files:**
- Create: `backend/pyproject.toml`, `backend/.env.example`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/data/cameras.json`, `backend/scripts/probe_clips.py`, `.gitignore`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces:
  - `Settings` (pydantic-settings, reads `backend/.env`): `anthropic_api_key: str | None`, `claude_model: str = "claude-opus-5-5"`, `twilio_account_sid/twilio_auth_token/twilio_from_number: str | None`, `police_number: str | None`, `gate_number: str | None`, `mode: Literal["live","replay"] = "live"`, `operator_name: str = "CMS Operator 1"`, `data_dir: Path = backend/data`, `db_path: Path = backend/data/incidents.db`
  - `CameraConfig` (pydantic): `id: str`, `name: str`, `location: str`, `clip: str | None` (filename in data_dir; None = "signal lost" tile), `analyse: bool`, `exits: dict[Literal["left","right","up","down"], str]` (image direction → exit name, e.g. `{"up": "Gate B"}`), `compass: dict[Literal["left","right","up","down"], str]` (image direction → compass word, e.g. `{"up": "north"}`)
  - `load_cameras(path: Path) -> list[CameraConfig]`; raises `ValueError` on duplicate ids or a missing clip file when `analyse` is true

- [ ] **Step 1:** Write `pyproject.toml`: Python `>=3.12,<3.13`; deps fastapi, uvicorn[standard], ultralytics, lap, opencv-python, numpy, anthropic, twilio, pydantic, pydantic-settings, python-dotenv, imageio-ffmpeg, torch, torchvision (torch and torchvision from explicit index `pytorch-cu128`); dev group pytest, httpx; `[tool.uv] package = false`; pytest `testpaths=["tests"]`, `pythonpath=["."]`. Root `.gitignore`: `backend/.venv`, `backend/data/*` except `!backend/data/cameras.json` and `!backend/data/.gitkeep`, `*.pt`, `backend/.env`, `frontend/node_modules`, `frontend/.next`.
- [ ] **Step 2:** Run `uv sync --python 3.12` in `backend/`, then `uv run python -c "import torch; print(torch.cuda.is_available())"`. Expected: `True`.
- [ ] **Step 3:** Write `scripts/probe_clips.py`, which prints fps, width × height, duration and codec (FourCC via OpenCV) for every `.mp4` in `data/`, and with `--transcode` re-encodes non-H.264 clips with the `imageio-ffmpeg` binary (`-c:v libx264 -pix_fmt yuv420p -movflags +faststart`). Run it on `case-1.mp4` and `case-2.mp4` and record the output in the README.
- [ ] **Step 4:** Write `data/cameras.json` with a 3×3 grid (9 cameras, CAM-01 … CAM-09, SDP-style names such as `Elmina Shoplot Row B`, `Bus Stop Jalan Elmina 2`). `case-1.mp4` and `case-2.mp4` are assigned with `analyse: true`; the other tiles have `clip: null` until more normal footage is added. **Ask the user which clip shows the snatch and which direction leads to which gate**; until then use placeholder `exits`/`compass` values and mark them `TODO-USER` in the README.
- [ ] **Step 5: Write the failing tests** `test_load_cameras_ok`, `test_load_cameras_duplicate_id_raises`, `test_load_cameras_missing_clip_raises_only_when_analysed`, and `test_settings_defaults_without_env` (asserting `claude_model == "claude-opus-5-5"` and `mode == "live"`).
- [ ] **Step 6:** Implement `app/config.py`. Run `uv run pytest tests/test_config.py -v`. Expected: PASS.
- [ ] **Step 7: Commit** `feat(backend): scaffold, settings, camera config, clip probe`.

---

### Task 2: Domain models and incident lifecycle

**Files:**
- Create: `backend/app/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces (all pydantic v2):
  - `Track`: `id: int`, `cls: Literal["person","motorcycle"]`, `bbox: tuple[float,float,float,float]` (x1,y1,x2,y2 in source pixels), `conf: float`, `keypoints: list[tuple[float,float,float]] | None` (COCO-17 x,y,conf; persons only)
  - `FrameDetections`: `camera_id: str`, `pts: float` (seconds since clip start), `frame_w: int`, `frame_h: int`, `tracks: list[Track]`, `loop: int` (loop counter, increments on wrap)
  - `CandidateEvent`: `camera_id`, `pts: float`, `loop: int`, `trigger: Literal["rule","model"]`, `suspect_track_ids: list[int]`, `victim_track_id: int | None`, `motorcycle_track_id: int | None`, `detected_at: datetime`
  - `VerificationResult`: exactly the spec §6.4 schema: `is_incident: bool`, `incident_type: Literal["snatch_theft","robbery","assault","other","none"]`, `confidence: float` (0–1), `summary: str`, `suspects: list[PersonDesc]` (`track_id: int | None`, `description: str`), `victim: PersonDesc | None`, `vehicle: VehicleDesc | None` (`type`, `colour`, `plate_visible: bool`, `plate_text: str | None`), `escape_direction: Literal["north","south","east","west","unknown"]`
  - `IncidentStatus` enum: `CANDIDATE, AI_REJECTED, PENDING_REVIEW, APPROVED, REJECTED, ESCALATED`
  - `EscalationStep`: `channel: Literal["police_call","police_sms","gate_sms"]`, `status: Literal["queued","ringing","in_progress","completed","sent","failed","skipped"]`, `detail: str | None`, `updated_at: datetime`
  - `Incident`: `id: str` (e.g. `INC-20261011-0001`), `camera_id`, `status`, `candidate: CandidateEvent`, `verification: VerificationResult | None`, `verification_error: str | None`, `escape_direction: str | None` (compass), `escape_exit: str | None`, `snapshot_files: list[str]`, `clip_file: str`, `clip_start: float`, `clip_end: float`, `guard_decision_at: datetime | None`, `operator: str | None`, `escalation: list[EscalationStep]`, `metrics: dict[str, float]` (keys `candidate_s`, `verified_s`, `shown_s`, `call_placed_s`), `created_at`
  - `transition(current: IncidentStatus, new: IncidentStatus) -> IncidentStatus`, raising `InvalidTransition` unless the move is one of: CANDIDATE→AI_REJECTED, CANDIDATE→PENDING_REVIEW, PENDING_REVIEW→APPROVED, PENDING_REVIEW→REJECTED, APPROVED→ESCALATED

- [ ] **Step 1: Write the failing tests:**
  - `test_valid_transitions` (every allowed move)
  - `test_invalid_transitions_raise` (e.g. REJECTED→APPROVED, PENDING_REVIEW→ESCALATED, APPROVED→APPROVED)
  - `test_verification_result_rejects_confidence_above_1`
  - `test_incident_json_roundtrip`
- [ ] **Step 2:** Run them. Expected: FAIL (import error).
- [ ] **Step 3:** Implement `app/models.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5: Commit** `feat(backend): domain models and incident lifecycle`.

---

### Task 3: Clip source and frame buffer

**Files:**
- Create: `backend/app/video/__init__.py`, `backend/app/video/source.py`, `backend/app/video/buffer.py`
- Test: `backend/tests/video/test_source.py`, `backend/tests/video/test_buffer.py` (tests generate a tiny synthetic MP4 with `cv2.VideoWriter` and `mp4v` into `tmp_path`)

**Interfaces:**
- Produces:
  - `ClipSource(path: Path, realtime: bool = True)`: iterator of `(frame: np.ndarray, pts: float, loop: int)`; loops forever; pts restarts at 0 on each loop and `loop` increments; when `realtime`, sleeps so frames come out at the clip's fps; `fps: float`, `size: tuple[int,int]`, `duration: float`; also `start_wall_time: float` (time.time() at loop 0 pts 0, updated each loop), used for frontend sync
  - `FrameBuffer(max_seconds: float = 10.0)`: `push(pts, loop, frame, detections: FrameDetections)`, `clear()`, `keyframes(center_pts: float, n: int = 8, span: float = 3.0, draw_tracks: bool = True) -> list[bytes]` (JPEG bytes, evenly spaced over `[center-span, center+span]` clamped to the buffer, boxes and track IDs drawn), `best_snapshot(track_id: int) -> bytes | None` (JPEG of the top 40% of the track's bbox, choosing the frame with the highest Laplacian variance; None if the track is not in the buffer)

- [ ] **Step 1: Write the failing tests:**
  - `test_source_loops_and_resets_pts` (a 1 s synthetic clip at realtime=False, read past its end: `loop` becomes 1 and pts restarts near 0)
  - `test_source_reports_fps_and_size`
  - `test_buffer_drops_frames_older_than_max_seconds`
  - `test_keyframes_returns_n_jpegs_within_span`
  - `test_best_snapshot_picks_sharpest` (push one blurred and one sharp frame for the same track; assert the sharp one's crop is returned, compared by Laplacian variance)
  - `test_best_snapshot_unknown_track_returns_none`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `source.py` and `buffer.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5: Commit** `feat(backend): clip source and frame buffer`.

---

### Task 4: Detector (YOLO track + pose)

**Files:**
- Create: `backend/app/detect/__init__.py`, `backend/app/detect/detector.py`
- Test: `backend/tests/detect/test_detector.py`

**Interfaces:**
- Consumes: `Track`, `FrameDetections` (Task 2)
- Produces:
  - `Detector(det_model: str = "yolo11s.pt", pose_model: str = "yolo11s-pose.pt", device: str = "cuda:0", conf: float = 0.35)`
  - `Detector.process(frame, camera_id, pts, loop) -> FrameDetections`: runs `model.track(frame, persist=True, tracker="bytetrack.yaml", classes=[0, 3])`, keeping COCO classes person=0 and motorcycle=3; runs the pose model on the same frame and attaches keypoints to person tracks via `attach_keypoints`
  - `Detector.reset()`: resets tracker state (called on a clip loop)
  - `attach_keypoints(tracks: list[Track], pose_boxes: list[bbox], pose_kpts: list[list[kp]], iou_min: float = 0.5) -> list[Track]`, a pure function that gives each person track the keypoints of the pose box with the highest IoU ≥ `iou_min`
- One `Detector` instance per analysed camera, since the tracker state is per stream.

- [ ] **Step 1: Write the failing tests:**
  - `test_attach_keypoints_matches_best_iou`
  - `test_attach_keypoints_ignores_low_iou`
  - `test_attach_keypoints_skips_motorcycles`
  - `test_process_on_real_clip_finds_person`, marked `@pytest.mark.gpu` and skipped if CUDA is unavailable or `data/case-1.mp4` is missing; it processes 30 frames and asserts at least one `person` track
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `detector.py` (Ultralytics downloads the weights on first use).
- [ ] **Step 4:** Run `uv run pytest tests/detect -v`. Expected: PASS, with the GPU test passing on this machine.
- [ ] **Step 5: Commit** `feat(backend): YOLO detector with tracking and pose`.

---

### Task 5: Rule B snatch trigger and escape direction

**Files:**
- Create: `backend/app/trigger/__init__.py`, `backend/app/trigger/base.py`, `backend/app/trigger/snatch_rule.py`, `backend/app/trigger/direction.py`
- Test: `backend/tests/trigger/test_snatch_rule.py`, `backend/tests/trigger/test_direction.py` (synthetic `FrameDetections` sequences built by a helper `make_scene(...)` in `tests/trigger/conftest.py`)

**Interfaces:**
- Consumes: `FrameDetections`, `CandidateEvent`, `CameraConfig`
- Produces:
  - `class Trigger(Protocol)`: `update(fd: FrameDetections, frame: np.ndarray | None = None) -> CandidateEvent | None`; `reset() -> None`. `SnatchRule` ignores `frame`; the Phase 2 action model needs it.
  - `SnatchRule(params: SnatchParams = SnatchParams())` implements `Trigger`
  - `SnatchParams` (dataclass, all tunable): `window_s=3.0`, `proximity_ratio=1.0` (motorcycle-to-pedestrian centre distance ≤ ratio × pedestrian bbox height), `reach_ratio=0.35` (rider wrist to pedestrian bbox distance ≤ ratio × pedestrian height), `jerk_ratio=0.25` (pedestrian centre displacement within 0.3 s ≥ ratio × own height), `accel_ratio=1.5` (motorcycle speed in the 1 s after contact ≥ ratio × speed in the 1 s before), `cooldown_s=10.0`, `min_track_frames=5`
  - `escape_direction(history: list[FrameDetections], motorcycle_track_id: int, camera: CameraConfig, lookback_s: float = 1.5) -> tuple[str, str] | tuple[None, None]`, which returns `(compass, exit_name)` from the dominant axis of the motorcycle's centre displacement (image `up` is negative y)

**Rule B algorithm (the part the signature does not determine):**
1. Classify persons: **riders** have a bbox centre inside a motorcycle bbox expanded by 20%, and are linked to that motorcycle; **pedestrians** are all other persons. Ignore tracks seen in fewer than `min_track_frames` frames.
2. **Contact:** a motorcycle comes within the proximity threshold of a pedestrian. Record the contact pts per (motorcycle, pedestrian) pair.
3. **Grab:** within `window_s` of contact, either a linked rider's wrist keypoint (COCO 9 or 10, conf ≥ 0.3) is within the reach threshold of the pedestrian bbox, **or** the pedestrian shows a jerk (step 1's displacement test). This keeps the rule working when pose fails.
4. **Getaway:** within `window_s` of contact, the motorcycle speed ratio passes `accel_ratio`, **or** the motorcycle-to-pedestrian distance increases to 2× the proximity threshold while moving away.
5. When contact, grab and getaway all happen within the window, emit `CandidateEvent(trigger="rule", suspect_track_ids=riders of that motorcycle, victim_track_id=pedestrian, motorcycle_track_id=moto)` at the getaway pts. Then suppress further events on that camera for `cooldown_s`.
6. **On a loop change** (`fd.loop` differs from the last one seen), call `reset()` before processing: clear all history, pairs and cooldown.

- [ ] **Step 1: Write the failing tests:**
  - `test_snatch_sequence_triggers_once` (contact → wrist reach → acceleration: exactly one event, with the right suspect, victim and motorcycle IDs)
  - `test_snatch_with_jerk_but_no_pose_triggers`
  - `test_motorcycle_passing_without_grab_no_trigger`
  - `test_pedestrians_walking_close_no_trigger` (no motorcycle)
  - `test_motorcycle_parked_near_pedestrian_no_trigger` (contact but no getaway)
  - `test_cooldown_suppresses_second_event`
  - `test_loop_change_resets_and_does_not_fire_on_wrap` (Review Focus 1)
  - `test_rider_not_treated_as_victim`
  - direction tests: `test_direction_up_maps_to_exit_and_compass`, `test_direction_unknown_when_track_missing`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `base.py`, `snatch_rule.py` and `direction.py`.
- [ ] **Step 4:** Run `uv run pytest tests/trigger -v`. Expected: PASS.
- [ ] **Step 5: Tune on real footage.** Write `scripts/debug_rule.py <clip>`: it runs Detector + SnatchRule with realtime=False and prints each event's pts, plus per-second contact, grab and getaway flags. Run it on the snatch clip: the event must land within ±1.5 s of the actual snatch. Run it on the normal clip: there must be no event. Adjust the `SnatchParams` defaults until both hold, and record the final values in the README.
- [ ] **Step 6: Commit** `feat(backend): Rule B snatch trigger and escape direction`.

---

### Task 6: Step 2 verifiers (Claude + mock)

**Files:**
- Create: `backend/app/verify/__init__.py`, `backend/app/verify/base.py`, `backend/app/verify/claude_verifier.py`, `backend/app/verify/mock_verifier.py`, `backend/app/verify/prompt.py`
- Test: `backend/tests/verify/test_claude_verifier.py`, `backend/tests/verify/test_mock_verifier.py`

**Interfaces:**
- Consumes: `CandidateEvent`, `VerificationResult`, `CameraConfig`, `Settings`
- Produces:
  - `class Verifier(Protocol)`: `async verify(candidate: CandidateEvent, keyframes: list[bytes], camera: CameraConfig) -> VerificationResult` (raises `VerificationUnavailable` on timeout, network error, refusal or schema failure)
  - `ClaudeVerifier(settings: Settings, client: anthropic.AsyncAnthropic | None = None, timeout_s: float = 12.0)`
  - `MockVerifier(fixtures_dir: Path)`: returns `data/mock_verifications/<camera_id>.json` if it exists, otherwise a built-in snatch-theft result with `confidence=0.9`
  - `make_verifier(settings) -> Verifier`: `ClaudeVerifier` if `anthropic_api_key` is set, otherwise `MockVerifier`
  - `build_prompt(candidate, camera) -> str` in `prompt.py`
- **Prompt content (fixed by the spec):** tell the model these are CCTV keyframes from `{camera.name}, {camera.location}`, in time order, with track IDs drawn on. Ask whether a crime is occurring, with the focus on motorcycle snatch theft. It must describe suspects by clothing, helmet and build only, never guess identity, ethnicity or names, and fill the schema. Use `escape_direction` only if clearly visible.
- **Request:** model `settings.claude_model`; images as base64 JPEG image blocks followed by a text block; `output_config` with `effort: "low"` and a JSON-schema format generated from `VerificationResult`; refusal fallbacks enabled. Check `stop_reason == "refusal"` before reading content. Exact SDK calls come from the `claude-api` skill.

- [ ] **Step 1: Write the failing tests** (using a fake client object with an async `messages` method that returns canned responses; no network):
  - `test_claude_verifier_parses_structured_result`
  - `test_claude_verifier_sends_n_images_and_camera_context` (inspect the fake's captured request: 8 image blocks, prompt contains camera name, model == settings.claude_model)
  - `test_claude_verifier_timeout_raises_unavailable` (Review Focus 3)
  - `test_claude_verifier_refusal_raises_unavailable`
  - `test_mock_verifier_uses_fixture_when_present`
  - `test_make_verifier_without_key_returns_mock`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement the verifiers.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** If an API key is available, run a manual check with `scripts/verify_once.py <clip> <pts>`: it grabs 8 keyframes around pts, calls `ClaudeVerifier` and prints the JSON and latency. Expected: `is_incident: true` on the snatch, and latency ≤ 6 s.
- [ ] **Step 6: Commit** `feat(backend): Claude and mock verifiers`.

---

### Task 7: Incident store and service

**Files:**
- Create: `backend/app/incidents/__init__.py`, `backend/app/incidents/store.py`, `backend/app/incidents/service.py`
- Test: `backend/tests/incidents/test_service.py`

**Interfaces:**
- Consumes: `Incident`, `IncidentStatus`, `transition`, `CandidateEvent`, `VerificationResult`, `EscalationStep`
- Produces:
  - `IncidentStore(db_path: Path)`: `save(incident)`, `get(id) -> Incident | None`, `list(status: IncidentStatus | None = None) -> list[Incident]` (newest first). It stores the incident JSON in one table `incidents(id TEXT PRIMARY KEY, status TEXT, created_at TEXT, body TEXT)`.
  - `IncidentService(store, snapshots_dir: Path, on_change: Callable[[Incident], Awaitable[None]])`, where `on_change` is called after every state change and is used for WebSocket broadcast:
    - `async open(candidate, camera, clip_file, snapshots: dict[int, bytes]) -> Incident`: writes snapshots to `snapshots_dir/<incident_id>_<track_id>.jpg`; sets `clip_start = max(0, pts-4)`, `clip_end = pts+3`; status CANDIDATE; records `metrics.candidate_s`
    - `async attach_verification(id, result: VerificationResult | None, error: str | None, direction: tuple[str|None,str|None]) -> Incident`: if the result says `is_incident` false, the status becomes AI_REJECTED and the snapshots are deleted; otherwise it becomes PENDING_REVIEW (including when `result` is None, in which case `verification_error` is set). Records `metrics.verified_s`.
    - `async approve(id, operator: str) -> Incident` and `async reject(id, operator: str) -> Incident`: both raise `InvalidTransition` when the incident isn't PENDING_REVIEW. Rejecting deletes the snapshot files.
    - `async mark_escalation(id, step: EscalationStep) -> Incident`: upserts a step by channel. When the police call reaches `ringing` or later, it records `metrics.call_placed_s` and moves APPROVED → ESCALATED.

- [ ] **Step 1: Write the failing tests:**
  - `test_open_writes_snapshots_and_sets_clip_window`
  - `test_verification_false_sets_ai_rejected_and_deletes_snapshots`
  - `test_verification_none_still_pending_review` (Review Focus 3)
  - `test_approve_twice_raises` and `test_approve_after_reject_raises` (Review Focus 4)
  - `test_reject_deletes_snapshots`
  - `test_mark_escalation_ringing_sets_escalated_and_metric`
  - `test_on_change_called_for_each_transition`
  - `test_store_roundtrip_and_list_order`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement the store and service.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5: Commit** `feat(backend): incident store and lifecycle service`.

---

### Task 8: Escalation (Twilio + dry run)

**Files:**
- Create: `backend/app/escalation/__init__.py`, `backend/app/escalation/script.py`, `backend/app/escalation/escalator.py`
- Test: `backend/tests/escalation/test_script.py`, `backend/tests/escalation/test_escalator.py`

**Interfaces:**
- Consumes: `Incident`, `CameraConfig`, `EscalationStep`, `IncidentService.mark_escalation`, `Settings`
- Produces:
  - `build_call_script(incident, camera, operator) -> str`. The spoken text includes: "This is an automated alert from Sime Darby Property Central Monitoring", incident type, camera location, time (HH:MM), suspect and vehicle description from the verification summary, escape direction and exit, "verified by {operator}", and is repeated once. If verification is None, it says "unverified by AI, confirmed by operator".
  - `build_sms(incident, camera, for_gate: bool) -> str` (≤ 320 characters). The gate version leads with "INTERCEPT: " plus the vehicle and suspect description and the exit.
  - `class Escalator(Protocol)`: `async escalate(incident: Incident, camera: CameraConfig) -> None`, which raises `NotApproved` unless `incident.status == APPROVED`
  - `TwilioEscalator(settings, service, client=None)`: places the police call with inline TwiML `<Response><Say voice="alice">…</Say></Response>`, sends the police SMS and the gate SMS, and polls call status every 2 s for up to 40 s, mapping Twilio statuses (queued, ringing, in-progress, completed, failed/busy/no-answer) to `EscalationStep` and calling `service.mark_escalation` on each change. An SMS failure marks that step `failed` and never raises. A missing gate number marks the gate step `skipped`.
  - `DryRunEscalator(service, delays=(0.5, 1.5, 4.0))`: simulates queued → ringing → completed for the call and `sent` for both SMS
  - `make_escalator(settings, service) -> Escalator`: Twilio if the SID, token, from-number and police number are all set, otherwise dry run

- [ ] **Step 1: Write the failing tests:**
  - `test_call_script_contains_location_description_exit_operator`
  - `test_call_script_unverified_wording`
  - `test_gate_sms_starts_with_intercept_and_fits_320`
  - `test_escalate_refuses_non_approved` (Guard approval constraint)
  - `test_twilio_escalator_maps_statuses` (fake Twilio client sequence queued→ringing→completed)
  - `test_sms_failure_does_not_raise`
  - `test_missing_gate_number_skipped`
  - `test_dry_run_emits_ringing_then_completed`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement the escalation module.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5: Commit** `feat(backend): Twilio and dry-run escalation`.

---

### Task 9: Pipeline orchestration, replay mode, API and WebSocket

**Files:**
- Create: `backend/app/pipeline.py`, `backend/app/ws.py`, `backend/app/main.py`, `backend/scripts/precompute.py`
- Test: `backend/tests/test_pipeline.py`, `backend/tests/test_api.py`

**Interfaces:**
- Consumes: everything above
- Produces:
  - `WsHub`: `connect(ws)`, `disconnect(ws)`, `async broadcast(msg: dict)`. Message types (all JSON with a `type` field):
    - `camera.sync` `{camera_id, loop, pts, wall_time}`, sent every 1 s per analysed camera
    - `detections` `{camera_id, loop, pts, frame_w, frame_h, tracks:[{id, cls, bbox, suspect: bool}]}`, sent every processed frame (keypoints not sent)
    - `incident.updated` `{incident: Incident}`, sent on every change, including creation
  - `CameraPipeline(camera, settings, detector, trigger, verifier, service, hub, buffer)` and `async run()`, with this loop: read frame → detect (via `asyncio.to_thread`) → buffer push → broadcast detections (marking `suspect=True` for track IDs in any open incident on this camera) → `trigger.update(fd, frame)` → on a candidate: take keyframes and snapshots, `service.open`, then in a **background task** `verifier.verify` (catching `VerificationUnavailable` and passing the error) and `escape_direction`, then `service.attach_verification`. On a loop change: `detector.reset()`, `trigger.reset()`, `buffer.clear()`.
  - `ReplayPipeline(camera, precomputed_path, service, hub)`, with the same messages and timing, driven by `precomputed/<camera_id>.json`: `{fps, frames:[FrameDetections…], candidates:[{candidate, verification, direction}]}`. Candidates are injected at their pts. Snapshots are stored next to the JSON as `precomputed/<camera_id>_<track_id>.jpg`.
  - `scripts/precompute.py <camera_id>` runs Detector + SnatchRule + verifier with realtime=False and writes the files above
  - REST (`main.py`):
    - `GET /api/cameras` → list[CameraConfig] plus `sync` info
    - `GET /api/incidents?status=` and `GET /api/incidents/{id}`
    - `POST /api/incidents/{id}/approve` and `/reject`, with body `{operator?: str}`; invalid transitions return 409; on approve, run `escalator.escalate` as a background task
    - `GET /media/clips/{file}` serves clips from `data_dir` **with HTTP Range support** (needed for `<video>` seeking; verify with `curl -r 0-99`)
    - `GET /media/snapshots/{file}`
    - `WS /ws`
  - On startup, one pipeline task per camera with `analyse: true`, live or replay depending on `settings.mode`

- [ ] **Step 1: Write the failing tests:**
  - `test_pipeline_candidate_creates_incident_and_verifies` (fake detector, fake trigger firing at frame 10, mock verifier: one incident reaches PENDING_REVIEW, and `incident.updated` is broadcast twice)
  - `test_pipeline_verifier_failure_still_pending_review`
  - `test_pipeline_loop_change_resets_components`
  - `test_replay_emits_same_message_types_as_live`
  - `test_api_approve_runs_escalation_once` (approve twice → second call returns 409, the escalator's fake is called once; Review Focus 4)
  - `test_api_clip_supports_range` (expects 206 and a `Content-Range` header)
  - `test_api_list_incidents_filters_by_status`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `ws.py`, `pipeline.py`, `main.py` and `precompute.py`.
- [ ] **Step 4:** Run `uv run pytest -v`. Expected: all PASS.
- [ ] **Step 5: Smoke test.** Run `uv run uvicorn app.main:app --port 8000`, then in another shell run `uv run python -c "import asyncio,websockets…"` (or use a browser WebSocket client) to see `camera.sync` and `detections` messages. Within one loop of the snatch clip, an `incident.updated` with status PENDING_REVIEW must appear.
- [ ] **Step 6: Commit** `feat(backend): pipeline, replay mode, REST and WebSocket API`.

---

### Task 10: Frontend scaffold, types, API client, WebSocket state

**Files:**
- Create: `frontend/` via `npx create-next-app@latest frontend --ts --tailwind --app --src-dir --eslint --no-import-alias`; then `src/lib/types.ts`, `src/lib/api.ts`, `src/lib/ws.ts`, `vitest.config.ts`; `.env.local.example` with `NEXT_PUBLIC_API_BASE=http://localhost:8000`
- Test: `frontend/src/lib/ws.test.ts`

**Interfaces:**
- Consumes: the backend message and REST shapes from Task 9 and the models from Task 2
- Produces:
  - `types.ts`: `Track`, `DetectionsMsg`, `SyncMsg`, `Incident`, `IncidentStatus`, `EscalationStep`, `VerificationResult`, `CameraConfig`, mirroring the backend field names exactly (snake_case kept)
  - `api.ts`: `getCameras()`, `getIncidents(status?)`, `getIncident(id)`, `approve(id, operator)`, `reject(id, operator)`, `clipUrl(file, start?, end?)` (which appends `#t=start,end`), `snapshotUrl(file)`
  - `ws.ts`: `cmsReducer(state: CmsState, msg: WsMsg) -> CmsState` (pure) and the hook `useCmsSocket(): { state, connected }`. It reconnects with backoff (1 s, 2 s, 5 s max) and, **on every (re)connect, reloads incidents via `getIncidents()`** (Review Focus 5).
  - `CmsState`: `incidents: Record<string, Incident>`, `detections: Record<cameraId, DetectionsMsg[]>` (the last 5 s, ordered by pts; cleared for a camera when a message arrives with a new `loop`), `sync: Record<cameraId, SyncMsg>`, `activeAlertId: string | null` (the oldest PENDING_REVIEW incident)

- [ ] **Step 1:** Scaffold the app, add Vitest, and check that `npm run dev` serves the default page.
- [ ] **Step 2: Write the failing tests:**
  - `reducer stores incident and sets activeAlertId for PENDING_REVIEW`
  - `reducer clears activeAlertId when incident approved or rejected and advances to next pending`
  - `reducer drops detections older than 5s`
  - `reducer clears camera detections when loop changes`
  - `reload after reconnect restores pending alert`
- [ ] **Step 3:** Run `npx vitest run`. Expected: FAIL.
- [ ] **Step 4:** Implement `types.ts`, `api.ts` and `ws.ts`.
- [ ] **Step 5:** Run `npx vitest run`. Expected: PASS.
- [ ] **Step 6: Commit** `feat(frontend): scaffold, API client, websocket state`.

---

### Task 11: Camera grid with synced box overlay

**Files:**
- Create: `frontend/src/lib/overlay.ts`, `frontend/src/components/CameraGrid.tsx`, `frontend/src/components/CameraTile.tsx`; modify `frontend/src/app/page.tsx`, `frontend/src/app/globals.css`, `frontend/src/app/layout.tsx`
- Test: `frontend/src/lib/overlay.test.ts`

**Interfaces:**
- Consumes: `CmsState`, `getCameras`, `clipUrl`
- Produces:
  - `fitTransform(frameW, frameH, boxW, boxH) -> { scale, offsetX, offsetY }`, matching `object-fit: contain` letterboxing
  - `nearestDetections(list: DetectionsMsg[], pts: number, maxGap = 0.25) -> DetectionsMsg | null`
  - `expectedPts(sync: SyncMsg, now: number, duration: number) -> number`, i.e. `(sync.pts + (now - sync.wall_time)) mod duration`
  - `<CameraTile camera detections sync alerting />`: a `<video muted loop playsInline>` of the clip, with a `<canvas>` overlay redrawn every animation frame from `nearestDetections(…, video.currentTime)`. If `|video.currentTime - expectedPts| > 0.3 s`, it sets `currentTime` to resync. Boxes are white with the track ID label, or red when `suspect`. The tile shows the camera ID and name top-left, a live clock with a red REC dot top-right, and a pulsing red border when `alerting`. A `clip: null` tile renders "SIGNAL LOST" over static noise styling.
  - `<CameraGrid />`: a 3×3 grid; the header shows the township name, the operator and a connection indicator

- [ ] **Step 1: Write the failing tests:**
  - `fitTransform letterboxes wide video in square box`
  - `nearestDetections returns null beyond maxGap`
  - `expectedPts wraps at duration`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement the overlay helpers and both components; set the dark control-room theme in `globals.css` (near-black background, slate panels, red accent, monospaced timestamps).
- [ ] **Step 4:** Run `npx vitest run`. Expected: PASS.
- [ ] **Step 5: Manual check.** With the backend running in live mode, open `http://localhost:3000`. Boxes must track people on the analysed tiles within about 1 video frame of visual lag, and must not show stale boxes right after the clip loops (Review Focus 1).
- [ ] **Step 6: Commit** `feat(frontend): camera grid with synced detection overlay`.

---

### Task 12: Alert card, approve/reject, escalation timeline

**Files:**
- Create: `frontend/src/components/AlertCard.tsx`, `frontend/src/components/EscalationTimeline.tsx`, `frontend/public/sounds/alert.mp3`; modify `frontend/src/app/page.tsx`
- Test: `frontend/src/components/AlertCard.test.tsx` (Vitest + @testing-library/react + jsdom)

**Interfaces:**
- Consumes: `CmsState.activeAlertId`, `approve`, `reject`, `clipUrl`, `snapshotUrl`
- Produces:
  - `<AlertCard incident camera onApprove onReject busy />`: a modal sliding in from the right with:
    - a looping replay `<video src={clipUrl(clip_file, clip_start, clip_end)}>`; on `timeupdate` past `clip_end`, it seeks back to `clip_start`
    - suspect snapshots
    - a summary line
    - a description table (suspects, vehicle, victim, escape direction → exit)
    - camera, location, time and confidence %
    - **Approve & escalate** (red) and **Reject (false positive)** (outline) buttons, both disabled while `busy`
  - The card plays the alert sound once when a new incident becomes active.
  - When `verification` is null, it shows the amber badge "AI verification unavailable: operator to confirm" and still shows the snapshots and clip.
  - `<EscalationTimeline steps />`: a stepper for Police call, Police SMS and Gate B alert, with icons for queued, ringing, completed, sent, failed and skipped

- [ ] **Step 1: Write the failing tests:**
  - `renders summary, exit and confidence`
  - `shows unverified badge when verification is null`
  - `buttons disabled while busy`
  - `approve calls onApprove once even on double click`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement both components and wire them into `page.tsx`. After Approve, the card stays open and shows the EscalationTimeline live until the call is `completed` or `failed`, then auto-closes after 5 s. A 409 response shows the toast "Already handled".
- [ ] **Step 4:** Run `npx vitest run`. Expected: PASS.
- [ ] **Step 5: Manual check, end to end, with zero credentials** (mock verifier + dry-run escalator): the snatch clip produces an alert card within 10 s; Approve walks the timeline; refreshing the page mid-alert brings the card back (Review Focus 5).
- [ ] **Step 6: Commit** `feat(frontend): alert card and escalation timeline`.

---

### Task 13: Incident log page

**Files:**
- Create: `frontend/src/components/IncidentTable.tsx`, `frontend/src/app/incidents/page.tsx`
- Test: `frontend/src/components/IncidentTable.test.tsx`

**Interfaces:**
- Consumes: `getIncidents`, `Incident`
- Produces: `/incidents`, a table of time, camera, type, status chip (colour per status), operator and response metrics (`candidate_s`, `verified_s`, `call_placed_s` formatted as seconds). It filters by status, including AI_REJECTED, so judges can see that Step 2 filtered false alarms. Clicking a row shows a detail panel with the clip replay, snapshots, the verification JSON as readable fields, and the escalation timeline.

- [ ] **Step 1: Write the failing tests:** `renders status chips and metrics`, `filters by status`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement the page and table, and add a header nav link "Incidents" from the CMS.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5: Commit** `feat(frontend): incident log`.

---

### Task 14: Demo hardening and runbook

**Files:**
- Create: `README.md` (root), `backend/data/mock_verifications/<camera_id>.json` for the snatch camera
- Modify: `backend/data/cameras.json` (final names, exits)

- [ ] **Step 1:** Run `scripts/precompute.py` for each analysed camera. Switch to `MODE=replay` and confirm the CMS looks identical to live mode.
- [ ] **Step 2:** Run the timing check over 3 runs of the snatch clip, from the `/incidents` metrics: snatch → card ≤ 10 s. Record the numbers in the README; they go into the pitch as evidence.
- [ ] **Step 3:** Run the false-alarm check: let the normal clip loop for 10 minutes and confirm 0 PENDING_REVIEW incidents. Report the AI_REJECTED count separately.
- [ ] **Step 4:** If Twilio credentials are available, test the real call and SMS to the verified numbers. Note the Malaysia geo-permission step in the README.
- [ ] **Step 5:** Write the README runbook: setup (uv, npm), `.env` variables, how to add clips and edit `cameras.json`, live vs replay, the pre-stage checklist (hotspot, verified numbers, replay files fresh, volume on for the alert sound), and the measured numbers.
- [ ] **Step 6: Commit** `docs: demo runbook and measured results`.

---

## Next

Phase 2: `docs/superpowers/plans/2026-10-11-cctv-alert-phase2-action-model.md`. The roadmap is in `docs/superpowers/plans/README.md`.
