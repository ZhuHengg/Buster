# Proactive CCTV Alert System: Phase 2 Implementation Plan (Gemini Step 1, then Action Model)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second Step 1 trigger that needs no training: Gemini Flash screens recent frames and raises a candidate when it sees a possible snatch. Measure it on the downloaded dataset. The VideoMAE action model (Part B) is kept as a deferred follow-up that reuses the same dataset, splits and metrics.

**Architecture:** Part A: `GeminiScreener` (frames → `ScreenResult`) is wrapped by `GeminiTrigger`, a `Trigger` that reads frames from the existing `FrameBuffer` and never blocks the video loop. `AnyTrigger` combines it with Rule B under one cooldown. The labelled dataset becomes a benchmark: `bench_screener.py` runs the screener over held-out videos and reports event recall and false triggers per hour. Part B (later): the same dataset trains VideoMAE, and `ActionModelTrigger` plugs into `AnyTrigger` next to the other two.

**Tech Stack:** Phase 1 stack plus `google-genai` (already added with the Gemini verifier). Part B adds Hugging Face `transformers` (VideoMAE) and `scikit-learn`.

**Spec:** `docs/SOLUTION_PLAN.md` §6.3 and §7. **Depends on:** Phase 1 complete, especially `Trigger`, `FrameBuffer`, `FrameDetections`, `CandidateEvent`, `CameraPipeline`, `scripts/precompute.py`, and the Gemini verifier (`app/verify/gemini_verifier.py`, `Settings.gemini_api_key`, `Settings.gemini_model`).

## Global Constraints

- All Phase 1 global constraints still apply (Python 3.12 via uv, Windows paths, no face recognition, nothing escalates without guard approval, zero-credential run).
- **Zero-credential run still works:** with no `GEMINI_API_KEY`, `make_trigger` returns Rule B only and logs one warning.
- **Demo clips are never used for training, validation, threshold selection or benchmarking.** Every clip referenced in `backend/data/cameras.json` is excluded by name and by phash. `case-1` and `case-2` are only run in Task A5, after the threshold is frozen.
- **Split by source video, never by clip or window.** No source video may appear in more than one split.
- **The live trigger must not block the video loop.** A Gemini call runs on a background thread; the loop only polls the result. Results older than `screen_max_lag_s` are discarded.
- **Step 1 is allowed to be wrong; Step 2 is the precision filter.** The screener prompt asks for high recall.
- **Latency budget changes:** snatch → alert card stays **≤ 10 s**. Step 1 is relaxed from ≤ 2 s to **≤ 4 s** because one Gemini round trip plus the screening interval cannot meet 2 s; Step 2 stays ≤ 6 s. Measured in Task A5, reported honestly if missed.
- Screener images: JPEG, **max width 640 px**, `screen_frames = 6` frames over the last 3.0 s.
- Targets on the held-out benchmark (spec §7, §8): **event recall ≥ 0.90** and a stated false-trigger rate per hour of normal footage. With small N these are indicative only, and the report must show the counts and a 95% Wilson interval.
- Datasets, windows, models and benchmark caches are git-ignored (`backend/data/datasets/`, `backend/data/windows/`, `backend/models/`, `backend/reports/*.jsonl`). Only scripts, `labels.csv` and metrics JSON are committed.
- Online clips are for training and testing only. Respect each dataset's license and platform terms; do not commit them.
- **API quota is a real limit.** One camera at the default 3 s interval is 20 calls/minute, plus Step 2. Check your key's rate limits before running with more than one analysed camera. Defaults must be safe for a free-tier key; the failure behaviour (backoff, not crash) is tested.

## Review Focus

1. **Gemini unreachable, rate-limited (429), blocked or returns junk:** the video loop keeps running, Rule B still works, and screening pauses for 30 s before retrying. Test in Task A3.
2. **Stale result after the clip loops:** a result computed for the previous loop must not raise a candidate in the new loop. Test in Task A3.
3. **Rule B and Gemini both fire for one snatch:** exactly one candidate, one incident, shared cooldown. Test in Task A3.
4. **Candidate with no track IDs:** Gemini may see a snatch that YOLO tracked poorly (this is the case-2 situation). The incident must still open and reach the guard; missing snapshots and escape direction must not crash anything. Test in Task A3.
5. **Hallucinated track IDs:** Gemini returns an ID that never existed. It is dropped, not stored. Test in Task A3.
6. **Benchmark cost and reruns:** a benchmark that silently makes thousands of paid calls, or repeats them when only the threshold changed. Cost estimate and cap before running, and a cache so reruns are free. Test in Task A4.
7. **Near-duplicate videos across splits:** the same viral clip under two names inflates recall. Group by phash before splitting. Test in Task A4.
8. **Bench vs live mismatch:** the benchmark has no YOLO boxes drawn on frames, the live pipeline does. The prompt must work with or without boxes; Task A5 re-checks on the live pipeline.

---

## File Structure

```
backend/
  training/                                  (Task 1 files already exist; see below)
    labels.py, ingest.py, label_tool.py, phash.py     DONE (commit 3352743)
    ingest.py            + --whole-video-label snatch|normal         (Task A1b)
    events.py            event_hits, choose_threshold, wilson_interval  (Task A4)
    splits.py            near-duplicate groups, group split, demo-clip guard  (Task A4)
    bench_screener.py    run GeminiScreener over a split, report metrics  (Task A4)
    # Part B (deferred): windows.py, build_dataset.py, dataset.py, train.py, evaluate.py
  app/trigger/
    gemini_screener.py   GeminiScreener, ScreenResult, ScreenUnavailable    (Task A2)
    gemini_trigger.py    GeminiTrigger                                       (Task A3)
    any_trigger.py       AnyTrigger                                          (Task A3)
    __init__.py          make_trigger                                        (Task A3)
    # Part B (deferred): action_model.py, scene.py
  app/video/buffer.py    keyframes(..., max_width)                           (Task A2)
  app/config.py          screen_* settings, triggers                         (Tasks A2, A3)
  data/labels.csv        committed
  reports/               screener_<split>.json committed, *.jsonl cache git-ignored
  tests/training/..., tests/trigger/...
docs/FILMING_GUIDE.md                        DONE
```

---

## Part A: Gemini Step 1 (build now)

### Task A1: Labels format, ingest, labelling tool, filming guide — DONE

Commit `3352743`. `LabelRow`, `read_labels`, `write_labels`, `validate_labels`, `ingest.py`, `label_tool.py`, `phash.py` and `docs/FILMING_GUIDE.md` exist. Do not redo.

**Human step (the user, not the agent) — revised.** Put the downloaded videos under `backend/data/datasets/` (`ucf_crime/{Robbery,Stealing,Normal_subset}`, `online/{snatch,normal}`, `staged/`). Datasets such as Snatch 1.0 or RoadCrime-CCTV go under `online/` unless you prefer `ucf_crime/`. Run `ingest.py` per folder and label snatch segments with `label_tool.py`; clips that are already trimmed to the event use Task A1b instead of the tool. **Minimum to run Task A4 (indicative numbers):** ≥ 15 snatch events from ≥ 10 distinct sources, and ≥ 30 minutes of normal footage. The VideoMAE minimum (Part B) is unchanged: 60 snatch segments from ≥ 40 sources and ≥ 2 hours normal.

### Task A1b: Whole-video label for pre-trimmed clips

**Files:**
- Modify: `backend/training/ingest.py`
- Test: `backend/tests/training/test_ingest.py`

**Interfaces:**
- Produces: `ingest_folder(..., whole_video_label: Literal["snatch","normal"] | None = None)`. When set, every unregistered video that would otherwise be "needs labelling" gets one row spanning `0..duration` with that label. CLI flag `--whole-video-label snatch|normal`. Videos already treated as normal by folder name keep their normal row. Existing rows are never changed.

- [ ] **Step 1:** Write failing tests `test_ingest_whole_video_label_snatch_adds_full_span_row` and `test_ingest_whole_video_label_skips_registered_files` (synthetic 2 s video in `tmp_path`).
- [ ] **Step 2:** Run `uv run pytest tests/training/test_ingest.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the parameter and the CLI flag in `ingest.py`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat(training): ingest whole-video labels for pre-trimmed clips`.

---

### Task A2: GeminiScreener

**Files:**
- Create: `backend/app/trigger/gemini_screener.py`
- Modify: `backend/app/video/buffer.py` (add `max_width`), `backend/app/config.py`, `backend/.env.example`
- Test: `backend/tests/trigger/test_gemini_screener.py`, `backend/tests/video/test_buffer.py` (extend)

**Interfaces:**
- Consumes: `Settings.gemini_api_key`, `Settings.gemini_model`, `CameraConfig`, the schema helper `_strict_schema` from `app/verify/claude_verifier.py`.
- Produces:
  - `Settings.gemini_screen_model: str | None = None` (falls back to `gemini_model`), `screen_threshold: float = 0.5`, `screen_interval_s: float = 3.0`, `screen_frames: int = 6`, `screen_max_lag_s: float = 6.0`. `.env.example` gets `GEMINI_SCREEN_MODEL=` (empty), `SCREEN_THRESHOLD`, `SCREEN_INTERVAL_S`.
  - `FrameBuffer.keyframes(center_pts, n=8, span=3.0, draw_tracks=True, max_width: int | None = None) -> list[bytes]`: when `max_width` is set and a frame is wider, resize it (keeping aspect) before JPEG encoding. Default behaviour is unchanged.
  - `class ScreenResult(BaseModel)`: `suspicious: bool`, `score: float` (0..1), `reason: str`, `suspect_track_ids: list[int]`, `motorcycle_track_id: int | None`, `victim_track_id: int | None`.
  - `class ScreenUnavailable(Exception)`.
  - `class GeminiScreener`: `__init__(settings, client: genai.Client | None = None, timeout_s: float = 8.0)`; `screen(frames: list[bytes], camera: CameraConfig) -> ScreenResult` is **synchronous** (it runs on a worker thread or in the benchmark). It uses `client.models.generate_content` with JSON-schema output, `thinking_budget=0`, and raises `ScreenUnavailable` on timeout, API error, block, empty text, or schema failure.
  - `build_screen_prompt(camera: CameraConfig) -> str`: states the camera name and location; says the frames are consecutive, oldest first, over about 3 s, may or may not have numbered boxes; asks whether a bag/phone/chain snatch by a person on a motorcycle (or on foot) is happening or just happened; says **to answer suspicious=true whenever it is plausible, because a second reviewer removes false alarms**; says normal traffic, people walking, parking, and a rider stopping to talk are not suspicious; says track IDs must be copied from the visible `#id` labels and left empty if none are visible.

- [ ] **Step 1: Write the failing tests** (fake client: `SimpleNamespace(models=FakeModels)` where `generate_content` returns an object with `.text` and `.prompt_feedback`):
  - `test_screen_parses_result`
  - `test_screen_sends_one_image_part_per_frame_and_prompt_last` (also asserts `camera.name` is in the prompt and "plausible" instruction is present)
  - `test_screen_timeout_raises_screen_unavailable`
  - `test_screen_api_error_raises_screen_unavailable` (uses `google.genai.errors.APIError(429, {...})`)
  - `test_screen_blocked_prompt_raises_screen_unavailable`
  - `test_screen_bad_json_raises_screen_unavailable`
  - `test_score_above_one_is_schema_failure`
  - `test_keyframes_max_width_downscales` (extend the buffer tests: a 1280×720 frame comes out 640 wide; without `max_width` it stays 1280)
- [ ] **Step 2:** Run `uv run pytest tests/trigger/test_gemini_screener.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the settings, `max_width`, and `gemini_screener.py`. Reuse `_strict_schema(ScreenResult)` for the response schema.
- [ ] **Step 4:** Run the tests plus the full suite `uv run pytest -q`. Expected: PASS, with the Phase 1 tests still green.
- [ ] **Step 5: Commit** `feat(trigger): GeminiScreener for step 1`.

---

### Task A3: GeminiTrigger, AnyTrigger, make_trigger, wiring

**Files:**
- Create: `backend/app/trigger/gemini_trigger.py`, `backend/app/trigger/any_trigger.py`; modify `backend/app/trigger/__init__.py` (add `make_trigger`), `backend/app/models.py` (`CandidateEvent.trigger: Literal["rule","model","llm"]`), `backend/app/config.py` (`triggers: Literal["rule","llm","both"] = "both"`), `backend/app/main.py` (`_build_pipelines` builds the trigger per camera via `make_trigger`), `backend/scripts/precompute.py` (use `make_trigger(..., blocking=True)`), and any frontend type that enumerates trigger values (`grep -rn "rule" frontend/src/lib/types.ts`).
- Test: `backend/tests/trigger/test_gemini_trigger.py`, `backend/tests/trigger/test_any_trigger.py`

**Interfaces:**
- Consumes: `Trigger` protocol (`update(fd: FrameDetections) -> CandidateEvent | None`, `reset()`), `FrameBuffer.keyframes(...)`, `GeminiScreener`, `ScreenResult`, `ScreenUnavailable`, `SnatchRule`.
- Produces:
  - `GeminiTrigger(settings, camera, buffer: FrameBuffer, screener: GeminiScreener | None = None, blocking: bool = False, cooldown_s: float = 10.0, backoff_s: float = 30.0)` implementing `Trigger`.
    - **Gate:** screening is considered only on frames that contain at least one `person` track.
    - **Cadence:** at most one screening per `settings.screen_interval_s` of `fd.pts`, and never while one is in flight.
    - **Request:** `buffer.keyframes(fd.pts, n=settings.screen_frames, span=3.0, max_width=640)`. Empty buffer → skip.
    - **Live (`blocking=False`):** the call runs on a single-thread executor; each `update` polls the future and returns at most one candidate.
    - **Blocking (`blocking=True`):** the call runs inline. Used by `precompute.py` and the benchmark, where video time runs faster than wall time.
    - **Fire rule:** result `suspicious` and `score >= settings.screen_threshold` and `fd.pts - request_pts <= settings.screen_max_lag_s` and the request's generation equals the current generation. The candidate's `pts` is the **request pts** (end of the screened window); `trigger="llm"`; `detected_at` is now.
    - **IDs:** `suspect_track_ids`, `motorcycle_track_id`, `victim_track_id` are kept only if the ID appeared in a detection within the last 4 s of `pts` (the trigger keeps its own small deque of recent track IDs); otherwise dropped.
    - **Failures:** `ScreenUnavailable` pauses screening for `backoff_s` of `fd.pts` and logs one warning; nothing is raised.
    - **Cooldown:** after a candidate, no further candidates for `cooldown_s`.
    - `reset()` clears state and increments the generation so in-flight results are discarded.
  - `AnyTrigger(triggers: list[Trigger], cooldown_s: float = 10.0)`: calls every trigger on every frame (so each keeps its own state), returns the first candidate, and suppresses all candidates from any trigger for `cooldown_s` after one is emitted. `reset()` resets all.
  - `make_trigger(settings: Settings, camera: CameraConfig, buffer: FrameBuffer, blocking: bool = False) -> Trigger`: `rule` → `SnatchRule()`; `llm` → `GeminiTrigger`; `both` → `AnyTrigger([SnatchRule(), GeminiTrigger])`. If `gemini_api_key` is missing, `llm` and `both` log one warning and return `SnatchRule()`.
  - `main.py`: `_build_pipelines` creates the `FrameBuffer` first and passes the same instance to `make_trigger` and `CameraPipeline`. The pipeline already pushes each frame to the buffer before calling `trigger.update`, so no pipeline change is needed.

- [ ] **Step 1: Write the failing tests** (fake screener with a scripted `screen()`; a real `FrameBuffer` filled with tiny frames; scenes built with the existing `make_scene` helper in `tests/trigger/conftest.py`):
  - `test_fires_when_screen_positive_blocking`
  - `test_below_threshold_does_not_fire`
  - `test_no_person_means_no_call` (screener call count stays 0)
  - `test_respects_interval_and_single_inflight` (live mode with a slow fake: call count matches the interval, never two at once)
  - `test_live_update_never_blocks` (slow fake of 0.5 s; each `update` returns in under 50 ms)
  - `test_stale_result_discarded_when_lagging` (Review Focus 2 and lag)
  - `test_result_from_previous_loop_discarded_after_reset` (Review Focus 2)
  - `test_unavailable_pauses_then_retries` (Review Focus 1: no raise, no call during `backoff_s`, a call after it)
  - `test_candidate_without_track_ids_is_valid` (Review Focus 4)
  - `test_hallucinated_track_ids_are_dropped` (Review Focus 5)
  - `test_cooldown_after_candidate`
  - `test_any_trigger_one_candidate_when_both_fire` (Review Focus 3)
  - `test_any_trigger_cooldown_applies_across_triggers`
  - `test_any_trigger_reset_resets_all`
  - `test_make_trigger_without_key_returns_rule` (Settings with `gemini_api_key=None`, `triggers="both"`)
  - `test_make_trigger_both_returns_any_trigger`
  - `test_pipeline_opens_incident_for_llm_candidate_without_ids` (end to end with `CameraPipeline`, fake detector, fake source, fake screener, `MockVerifier`: the incident reaches `PENDING_REVIEW`, no exception, direction is `(None, None)`)
- [ ] **Step 2:** Run `uv run pytest tests/trigger -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `gemini_trigger.py`, `any_trigger.py`, `make_trigger`, the model/config changes and the wiring. Update the frontend trigger type if one exists and run `npm test` in `frontend/`.
- [ ] **Step 4:** Run the full backend suite `uv run pytest -q` and `npm test` (frontend). Expected: all PASS.
- [ ] **Step 5: Commit** `feat(trigger): GeminiTrigger combined with Rule B`.

---

### Task A4: Benchmark the screener on the dataset

**Files:**
- Create: `backend/training/events.py`, `backend/training/splits.py`, `backend/training/bench_screener.py`
- Test: `backend/tests/training/test_events.py`, `backend/tests/training/test_splits.py`, `backend/tests/training/test_bench_screener.py`

**Interfaces:**
- Consumes: `LabelRow`, `read_labels`, `load_cameras`, `GeminiScreener`, `hamming` from `training/phash.py`.
- Produces:
  - `events.event_hits(scores: list[tuple[float, float]], events: list[tuple[float, float]], threshold: float, consecutive: int = 2, tolerance_s: float = 1.5, cooldown_s: float = 10.0) -> tuple[int, int]` returning `(hits, false_triggers)`. `scores` are `(time_s, p_snatch)`. A trigger is `consecutive` consecutive scores ≥ threshold; it is a hit if its time is within `[event.start - tolerance_s, event.end + tolerance_s]`, otherwise a false trigger; triggers within `cooldown_s` of the previous one are merged. Each event counts as hit at most once.
  - `events.VideoScores = tuple[list[tuple[float, float]], list[tuple[float, float]], float]` (scores, events, hours of footage).
  - `events.choose_threshold(videos: list[VideoScores], max_false_per_hour: float = 2.0, **hit_kwargs) -> float`: the lowest threshold (searched over the distinct score values) whose false triggers per hour ≤ the limit; ties go to higher event recall.
  - `events.wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]`.
  - `splits.source_groups(rows: list[LabelRow], max_hamming: int = 6) -> list[list[str]]`: groups of `source_id` whose phashes are within `max_hamming` (union-find).
  - `splits.split_sources(rows, seed: int = 42, fractions: tuple[float, float, float] = (0.7, 0.15, 0.15)) -> dict[str, str]`: `source_id → "train"|"val"|"test"`, whole groups together, greedy so each split gets at least one snatch source when there are ≥ 3 snatch groups.
  - `splits.assert_no_demo_clips(rows, cameras) -> None`: raises `ValueError` if a row's file name equals a camera clip, or its phash is within 6 of a demo clip's phash (the demo phash is computed from `backend/data/<clip>`).
  - `bench_screener.py --labels data/labels.csv --split val|test|all [--stride-s 3.0] [--max-calls 1500] [--cache reports/screener_cache.jsonl] [--out reports/screener_<split>.json]`:
    1. Loads labels, runs `assert_no_demo_clips`, takes the sources of the requested split from `split_sources`. (`--split all` is only for smoke runs and is not reported.)
    2. For each source video, steps through time every `stride_s`, builds 6 JPEGs over the last 3 s at max width 640, no boxes, and calls `GeminiScreener.screen`. Snatch videos are scored over the whole file; the events are the snatch segments.
    3. Prints the number of planned calls first. Exits with code 2 and calls nothing if it exceeds `--max-calls`.
    4. Caches each result in the JSONL cache keyed by `(file, t, model, prompt_hash)`. A rerun reads the cache and makes no API call.
    5. With `--split val` it picks the threshold with `choose_threshold(..., consecutive=1, tolerance_s=3.0)` and writes `reports/screener_threshold.json`. With `--split test` it reads that file and fails if it is missing.
    6. Writes the report JSON: events, hits, event recall with `wilson_interval`, normal hours, false triggers, false triggers per hour, the threshold, the model ID, the prompt hash, call count, per-origin counts, and the list of missed events (file, start, end, best score).

- [ ] **Step 1: Write the failing tests:**
  - `test_event_hits_counts_hit_within_tolerance`
  - `test_event_hits_single_score_below_consecutive_not_trigger`
  - `test_event_hits_merges_within_cooldown`
  - `test_event_hits_counts_each_event_once`
  - `test_choose_threshold_respects_false_rate`
  - `test_choose_threshold_prefers_recall`
  - `test_wilson_interval_known_values` (for example 9 of 10 → about (0.60, 0.98))
  - `test_source_groups_merges_near_duplicates` (Review Focus 7)
  - `test_split_sources_no_source_in_two_splits_and_groups_together`
  - `test_assert_no_demo_clips_by_name_and_phash`
  - `test_bench_refuses_over_max_calls_and_makes_no_calls` (Review Focus 6)
  - `test_bench_second_run_uses_cache_and_makes_no_calls` (Review Focus 6)
  - `test_bench_test_split_requires_threshold_file`
  
  The bench tests use 4–6 synthetic videos in `tmp_path` and a fake screener injected through a `screener` parameter of the module's `run(...)` function (the CLI calls `run`).
- [ ] **Step 2:** Run `uv run pytest tests/training -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `events.py`, `splits.py`, `bench_screener.py`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5 (needs the downloaded dataset and `GEMINI_API_KEY`):** run `uv run python -m training.bench_screener --split val`, read the planned-call number it prints, then run it for real; then `--split test`. Commit both report JSONs. If recall is below 0.90, read the missed-events list, then change only `build_screen_prompt`, delete nothing from the cache (the prompt hash changes the key), and rerun `--split val` first. Do not tune on `--split test`. Record each round in `backend/reports/SCREENER_ROUNDS.md` (prompt hash, model, val and test numbers).
- [ ] **Step 6: Commit** `feat(training): events, splits and Gemini screener benchmark`.

---

### Task A5: Live check on the demo clips and docs

**Files:**
- Create: `backend/scripts/debug_trigger.py`
- Modify: `README.md` (results, runbook, env vars), `docs/superpowers/plans/README.md` (roadmap rows), `docs/superpowers/plans/2026-10-11-cctv-alert-phase3-evidence-scale.md` (the `make_trigger` consumes line, now `make_trigger(settings, camera, buffer, blocking)`; `settings.triggers` values `rule|llm|both`)

**Interfaces:**
- `debug_trigger.py <clip> [--camera CAM-02] [--triggers rule|llm|both]`: runs the real `Detector` and `make_trigger(..., blocking=True)` over the clip with the threshold from `reports/screener_threshold.json`, and prints each candidate's trigger source, pts, and the delay from the labelled snatch time (`--snatch-at <seconds>`).

- [ ] **Step 1:** Run `debug_trigger.py data/case-2.mp4 --triggers llm --snatch-at 6.4` and `data/case-1.mp4 --triggers llm`. Expected: a candidate within 4 s of the snatch on case-2 and no candidate on case-1. **Threshold and prompt stay frozen. If case-2 is missed, report the Gemini scores honestly and say so in the README; do not tune on it.**
- [ ] **Step 2:** Regenerate replay files: `uv run python scripts/precompute.py CAM-02` with `TRIGGERS=both`.
- [ ] **Step 3:** Repeat the Phase 1 Task 14 checks: snatch → card ≤ 10 s over 3 runs; the normal clip looping for 10 minutes gives 0 `PENDING_REVIEW`. Record how many candidates came from `rule` and `llm`, how many Step 2 rejected, and the Gemini calls per minute observed.
- [ ] **Step 4:** Update the README (env vars `GEMINI_*`, `SCREEN_*`, `TRIGGERS`; the benchmark numbers with counts and intervals; the demo checks; the quota note), the roadmap README, and the Phase 3 consumes line.
- [ ] **Step 5: Commit** `docs: phase 2 gemini step 1 results`.

---

## Part B: VideoMAE action model (deferred)

**Do not start until Part A is committed and you decide there is time.** Why you would: Gemini screening costs API calls and 1–3 s per round trip; a local model has neither. The dataset, `labels.csv`, `splits.py`, `events.py` and the benchmark metrics from Part A are reused, so the two triggers are compared on the same held-out videos.

**Extra Global Constraints for Part B**
- Window: **16 frames sampled evenly over 2.0 s**, resized so the shorter side is 224, centre-cropped to 224×224.
- Model: `MCG-NJU/videomae-base-finetuned-kinetics`, head replaced for 2 labels `["normal", "snatch"]` (order fixed everywhere). Fallback if it will not train on the RTX 3080 (16 GB) at batch ≥ 2 with fp16: batch 2 with accumulation 8, then torchvision `r2plus1d_18` (Kinetics weights).
- Targets: event recall ≥ 0.90 on the same test split Gemini was benchmarked on, and Step 1 ≤ 2 s at runtime while YOLO runs on the same GPU.
- Dependencies `transformers>=5.19.0` and `scikit-learn>=1.9.1` are already in `pyproject.toml`.

**Review Focus for Part B**
1. Segments shorter than one window, or videos shorter than 2 s: skipped with a warning, no crash, no padding.
2. Class imbalance (about 10:1): weighted loss, and per-class metrics instead of plain accuracy.
3. GPU contention at runtime: stale windows are dropped, never queued.
4. All three triggers fire for one event: one candidate (already covered by `AnyTrigger` tests; extend them).

### Task B1: Window sampling and dataset build

**Files:** Create `backend/training/windows.py`, `backend/training/build_dataset.py`. Test `backend/tests/training/test_windows.py`, `test_build_dataset.py`.

**Interfaces:**
- Consumes: `LabelRow`, `read_labels`, `load_cameras`, and `splits.source_groups`, `splits.split_sources`, `splits.assert_no_demo_clips` from Task A4 (do not reimplement them).
- Produces:
  - `sample_indices(start_s, fps, n=16, span_s=2.0) -> list[int]`
  - `preprocess(frames: list[np.ndarray], size=224, crop: tuple[int,int,int,int] | None = None) -> np.ndarray` (uint8 `[16,224,224,3]`, RGB; a given `crop` is padded to a square with edge pixels first). **Single source of preprocessing for training and runtime.**
  - `read_window(path, start_s, ...) -> np.ndarray | None` (None if the video is too short)
  - `build_dataset.py --labels data/labels.csv --out data/windows/ [--stride-pos 0.25] [--stride-neg 1.0] [--seed 42]`: demo guard, splits from `split_sources`, positive windows overlapping a snatch segment by ≥ 50%, negative windows from normal segments plus hard negatives ≥ 2 s from a snatch segment, writes `windows/<split>/<label>/<source_id>_<start_ms>.npy` and `index.csv` (`path, split, label, source_id, origin, start`), prints counts per split, label and origin.

- [ ] **Step 1:** Write failing tests: `test_sample_indices_even_spacing`, `test_preprocess_shape_and_dtype`, `test_preprocess_with_crop_pads_to_square`, `test_read_window_short_video_returns_none`, `test_build_hard_negatives_away_from_segment`, `test_build_skips_segment_shorter_than_window_with_warning`, `test_build_uses_the_same_split_as_bench` (the split of every source equals `split_sources(rows)`).
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `windows.py` and `build_dataset.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Run the real build. Expected: no errors and every split has ≥ 1 snatch source. Record counts in `backend/models/action/dataset_stats.json`.
- [ ] **Step 6: Commit** `feat(training): window sampling and dataset build`.

### Task B2: Training

**Files:** Create `backend/training/dataset.py`, `backend/training/train.py`. Test `backend/tests/training/test_dataset.py`, `test_train_smoke.py`.

**Interfaces:**
- Consumes: `index.csv` and windows from Task B1.
- Produces:
  - `WindowDataset(index_csv, split, augment: bool)` returning `(tensor [16,3,224,224] float, label int)` normalised with the VideoMAE image processor mean and std. When `augment`, applied identically across the 16 frames: horizontal flip (p 0.5), brightness and contrast ±25%, Gaussian blur (p 0.2), JPEG re-compression quality 30–70 (p 0.3), random resized crop scale 0.8–1.0.
  - `class_weights(index_csv, split="train") -> torch.Tensor` (inverse frequency, normalised).
  - `train.py --arch videomae|r2plus1d --epochs 15 --batch 4 --accum 4 --lr 5e-5 --out models/action/ [--max-steps N]`: AdamW, cosine schedule with 10% warmup, fp16 autocast, weighted cross-entropy; evaluates val each epoch, keeps the best val snatch F1, early stopping patience 4; saves `model/`, `train_log.csv`, `labels.json`, `arch.json`.

- [ ] **Step 1:** Write failing tests: `test_dataset_item_shape_and_label`, `test_augment_same_flip_for_all_frames`, `test_class_weights_favour_minority`, `test_train_smoke_runs_two_steps` (`--arch r2plus1d --max-steps 2 --batch 2` on CPU with a tiny synthetic windows folder; the output files exist).
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `dataset.py` and `train.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Run the real training. On out-of-memory use `--batch 2 --accum 8`, then `--arch r2plus1d`.
- [ ] **Step 6: Commit** `feat(training): action model fine-tuning` (code and `train_log.csv`, not weights).

### Task B3: Evaluation

**Files:** Create `backend/training/evaluate.py`. Test `backend/tests/training/test_evaluate.py`.

**Interfaces:**
- Consumes: the trained model folder, `index.csv`, `labels.csv`, and `events.event_hits`, `events.choose_threshold`, `events.wilson_interval` from Task A4.
- Produces: `evaluate.py --model models/action/ --split val|test`: scores every video of the split end to end with a 0.5 s stride, writes `models/action/metrics_<split>.json` (per-class window precision, recall and F1, confusion matrix, event recall with interval, false triggers per hour, threshold, event and hour counts); with `--split val` also writes `threshold.json`. Uses `consecutive=2`, `tolerance_s=1.5`.

- [ ] **Step 1:** Write failing tests: `test_evaluate_reports_per_class_not_only_accuracy`, `test_evaluate_val_writes_threshold_json` (tiny fake model callable and two synthetic videos).
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `evaluate.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Run `--split val`, then `--split test`. Target event recall ≥ 0.90. If short, add data or hard negatives and repeat B1–B3, logging each round in `models/action/ROUNDS.md`.
- [ ] **Step 6: Commit** `feat(training): event-level evaluation of the action model`.

### Task B4: ActionModelTrigger

**Files:** Create `backend/app/trigger/action_model.py`, `backend/app/trigger/scene.py`; modify `snatch_rule.py` (import `classify_persons`), `backend/app/trigger/__init__.py` (extend `make_trigger`), `backend/app/config.py` (`triggers: Literal["rule","llm","model","both","all"]`, `action_model_dir: Path = backend/models/action`). Test `backend/tests/trigger/test_action_model.py`.

**Interfaces:**
- Consumes: `Trigger` (`update(fd)` only; **it has no `frame` argument**, so like `GeminiTrigger` this trigger reads frames from the shared `FrameBuffer`), `windows.preprocess`, `sample_indices`, `threshold.json`.
- Produces:
  - `scene.classify_persons(fd: FrameDetections) -> tuple[dict[int, int], list[int]]` (rider track → motorcycle track, pedestrian track IDs), moved out of `snatch_rule.py`; the existing `SnatchRule` tests must still pass.
  - `ActionModelTrigger(settings, buffer, model_dir: Path, device="cuda:0", stride_s=0.5, consecutive=2, cooldown_s=10.0, max_lag_s=1.0, scorer: Callable[[np.ndarray], float] | None = None)` implementing `Trigger`. Every `stride_s` of pts it takes 16 frames over the last 2.0 s from the buffer, crops to the union box of motorcycles and people near them (padded by 25%, full frame if none), scores on a single worker thread, fires after `consecutive` scores ≥ threshold, drops stale results and queued windows (keeps only the newest).
  - `make_trigger`: `model` → `ActionModelTrigger`; `all` → `AnyTrigger([SnatchRule, GeminiTrigger, ActionModelTrigger])`. A missing model folder or `threshold.json` logs a warning and drops that trigger from the list.

- [ ] **Step 1:** Write failing tests: `test_fires_after_two_consecutive_high_scores`, `test_single_high_score_does_not_fire`, `test_crop_region_covers_motorcycle_and_nearby_pedestrian`, `test_crop_full_frame_when_no_motorcycle`, `test_stale_result_discarded_when_lagging`, `test_busy_worker_keeps_only_newest_window`, `test_reset_clears_state_on_loop`, `test_any_trigger_one_candidate_when_three_fire`, `test_make_trigger_all_drops_missing_model`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `scene.py`, `action_model.py` and the `make_trigger` extension.
- [ ] **Step 4:** Run the full suite. Expected: all PASS.
- [ ] **Step 5:** Measure with `scripts/debug_trigger.py <clip> --triggers model`. Expected: ≤ 2 s after the snatch on the snatch clip, nothing on the normal clip.
- [ ] **Step 6: Commit** `feat(backend): action model trigger`.

### Task B5: Compare and decide

- [ ] **Step 1:** Run `bench_screener.py --split test` (cached, free) and `evaluate.py --split test` side by side. Add a table to the README: Rule B, Gemini, VideoMAE, all three. Columns: event recall with interval, false triggers per hour, median delay, cost per hour of footage.
- [ ] **Step 2:** Regenerate replay files with `TRIGGERS=all`, repeat the Task A5 demo checks, update the README.
- [ ] **Step 3: Commit** `docs: phase 2 action model results`.
