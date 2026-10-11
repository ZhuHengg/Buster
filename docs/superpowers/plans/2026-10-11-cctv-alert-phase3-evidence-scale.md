# Proactive CCTV Alert System: Phase 3 Implementation Plan (Evidence, Scale, Feedback Loop)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the working system into measured evidence for the judges, and finish the product loop:
- a repeatable benchmark (detection recall, false alarms, latency per stage)
- a scale test (cameras per GPU)
- a Results page in the CMS
- a guard feedback loop, where rejected alerts become new training data
- a frozen, rehearsed demo build

**Architecture:**
- `scripts/benchmark.py` runs the real pipeline offline over the labelled test sources and the demo clips and writes `backend/reports/benchmark.json`.
- `scripts/scale_test.py` runs N simultaneous camera pipelines on the GPU and writes `backend/reports/scale.json`.
- A `GET /api/reports` endpoint serves both reports plus a user-editable `baseline.json`; a `/results` page in the CMS shows them.
- `scripts/export_feedback.py` turns guard-rejected and AI-rejected incidents into `labels.csv` rows with origin `feedback`, which feed the Phase 2 dataset build.

**Tech Stack:** Phase 1 and 2 stacks. Charts on `/results` use plain SVG/React (no chart library needed for KPI tiles and one bar chart). **Read the `dataviz` skill before building the Results page.**

**Spec:** `docs/SOLUTION_PLAN.md` §8 (measures of success), §2 goals ("prove it is not rigged"), `docs/PROBLEM_STATEMENT.md` (success measures, baseline number). **Depends on:** Phase 1 complete. Phase 2 is optional: every task works with `TRIGGERS=rule`, and reports state which triggers were active.

## Global Constraints

- All Phase 1 and 2 global constraints still apply.
- **Reports must be reproducible:** every report JSON records the git commit, triggers, verifier type (claude or mock), model ID, threshold, the clips and sources used, and a UTC timestamp.
- **Demo clips are reported separately from the test set** and are never mixed into test-set numbers.
- **Baseline numbers come from the user's interviews,** not from code. `backend/reports/baseline.json` is hand-edited, e.g. `{"time_to_notice_s": null, "source": "guard interviews, n=…"}`. The Results page shows "baseline pending" when a value is null, and **never invents a number**.
- Feedback export never deletes or edits existing `labels.csv` rows; it only appends, and skips incidents already exported.
- Snapshots of rejected incidents are already deleted (Phase 1). The feedback export uses only the clip file, `clip_start` and `clip_end`, never snapshots.

## Review Focus

1. **Benchmark run with the mock verifier:** numbers would look perfect but mean nothing. The report must label the verifier type clearly, and the Results page shows a warning banner when the verifier is the mock. Test in Task 1 and Task 3.
2. **Scale test exhausting GPU memory as N grows:** it must record the failure point and stop cleanly, not crash the machine or leave zombie processes. Test in Task 2.
3. **Missing report files:** a fresh clone has no reports. The API returns 200 with `null` sections, and the page shows how to generate them. Test in Task 3.
4. **Feedback export run twice:** no duplicate rows (idempotent by incident ID). Test in Task 4.
5. **AI-rejected candidates that were actually real snatches:** an AI-rejected incident is not automatically a negative. Export AI_REJECTED only after a human confirms via the `--confirm` review. Guard-REJECTED incidents export directly. Test in Task 4.

---

## File Structure

```
backend/
  scripts/benchmark.py        offline end-to-end benchmark → reports/benchmark.json
  scripts/scale_test.py       N-camera throughput test → reports/scale.json
  scripts/export_feedback.py  incidents → labels.csv rows (origin=feedback)
  app/reports.py              load/validate report files for the API
  app/main.py                 + GET /api/reports
  app/config.py               + analyse_fps (frame skipping for scale)
  app/pipeline.py             + honour analyse_fps
  reports/baseline.json       committed, hand-edited
  reports/*.json              generated (git-ignored except baseline.json)
  tests/test_benchmark.py, test_scale_test.py, test_reports_api.py, test_export_feedback.py
frontend/
  src/app/results/page.tsx
  src/components/KpiTile.tsx, LatencyBars.tsx, ScaleChart.tsx
README.md                     final runbook + results
```

---

### Task 1: End-to-end benchmark

**Files:**
- Create: `backend/scripts/benchmark.py`, `backend/reports/.gitkeep`
- Test: `backend/tests/test_benchmark.py`

**Interfaces:**
- Consumes: `Detector`, `make_trigger`, `make_verifier`, `escape_direction`, `FrameBuffer`, `read_labels`, `load_cameras`. **If Phase 2 was skipped:**
  - `make_trigger` and `read_labels` don't exist yet. First add `make_trigger(settings) -> Trigger` in `app/trigger/__init__.py`, returning `SnatchRule()` for any setting, plus `settings.triggers` defaulting to `"rule"`.
  - Then create a minimal `training/labels.py` with `LabelRow`, `read_labels` and `write_labels` exactly as specified in Phase 2 Task 1, and label the test events with any video player.
- Produces:
  - `run_source(path, events: list[tuple[float,float]], components) -> SourceResult`, where `SourceResult` has: `source_id`, `hours`, `events`, `hits`, `step1_candidates`, `step1_false`, `step2_confirmed`, `step2_false`, `ai_filtered`, and `latencies: list[{"event_to_candidate_s","candidate_to_verified_s"}]`. The video is processed with realtime=False, but latencies are measured in **video time** for detection plus **wall time** for verification.
  - `aggregate(results: list[SourceResult]) -> dict`, which computes:
    - `event_recall_step1` and `event_recall_final` (after Step 2)
    - `false_per_hour_step1` and `false_per_hour_final`
    - `ai_filter_rate` (Step 1 false triggers removed by Step 2 ÷ Step 1 false triggers)
    - p50 and p90 of each latency
    - `detection_to_card_p50_s`, which adds the measured UI push time (a constant 0.3 s, documented)
  - CLI: `benchmark.py --set test|demo|both [--verifier claude|mock] [--triggers rule|model|both]` writes `reports/benchmark.json` as `{meta: {...reproducibility fields...}, test: {...}|null, demo: {per_clip: [...]}|null}`.
  - For the test set, events come from the `labels.csv` snatch segments of test-split sources (the split from Phase 2's `index.csv`; if Phase 2 has not been done, every labelled source counts as test).
  - For the demo set, the expected event comes from `cameras.json`: add an optional `expected_event: {"start": s, "end": s} | null` per camera, where null means a normal clip.

- [ ] **Step 1: Write the failing tests** (using fake detector, trigger and verifier components over a synthetic video):
  - `test_aggregate_recall_and_false_rate`
  - `test_ai_filter_rate`
  - `test_latency_percentiles`
  - `test_report_meta_includes_commit_verifier_triggers` (Review Focus 1)
  - `test_demo_normal_clip_counts_any_candidate_as_false`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `benchmark.py`, and add `expected_event` to `CameraConfig` (optional, default None) and to `cameras.json`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Run `uv run python scripts/benchmark.py --set both --verifier claude` if a key is available, otherwise `--verifier mock`. The report must exist and print a summary table.
- [ ] **Step 6: Commit** `feat(backend): end-to-end benchmark`.

---

### Task 2: Scale test and frame-skip setting

**Files:**
- Create: `backend/scripts/scale_test.py`; modify `backend/app/config.py` (`analyse_fps: float | None = None`, where None means every frame), `backend/app/pipeline.py` (skip frames so detection runs at ≤ `analyse_fps`; the skipped frames are still buffered for keyframes)
- Test: `backend/tests/test_scale_test.py`, `backend/tests/test_pipeline.py` (add `test_analyse_fps_skips_frames`)

**Interfaces:**
- Produces:
  - `scale_test.py --clip <file> --max-cameras 16 --seconds 60 [--analyse-fps 10]`. For N = 1, 2, 4, 8, 12, 16 it runs N `CameraPipeline`s (the same clip, the dry-run verifier and escalator, no WebSocket clients) in one process for `--seconds` and measures:
    - achieved analysis fps per camera (mean, min)
    - GPU memory peak (`torch.cuda.max_memory_allocated`)
    - p90 frame lag, i.e. how far processing falls behind the clip clock
  - It stops increasing N at the first N where mean fps < 0.9 × target, or p90 lag > 1 s, or a CUDA OOM (caught; `torch.cuda.empty_cache()`; recorded as `"oom": true`) (Review Focus 2).
  - It writes `reports/scale.json`: `{meta, target_fps, rows: [{n, fps_mean, fps_min, lag_p90_s, gpu_mem_gb, ok}], max_cameras_ok}`.
  - Each N runs in a **fresh subprocess**, so state and memory don't leak between runs. The parent kills the child on timeout (`--seconds` + 60 s).

- [ ] **Step 1: Write the failing tests:**
  - `test_analyse_fps_skips_frames` (a 30 fps fake source with `analyse_fps=10` → detector called on about 1/3 of frames, buffer gets all frames)
  - `test_scale_stop_rule_on_low_fps`
  - `test_scale_stop_rule_on_oom` (fake runner raising an OOM-like error)
  - `test_scale_report_schema`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement the frame skip and `scale_test.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Run the real test: `uv run python scripts/scale_test.py --clip <snatch clip> --analyse-fps 10`. Record `max_cameras_ok` in the README. **The pitch line it supports:** "One laptop-class GPU analyses X cameras at 10 fps; a township with N cameras needs about N/X GPUs."
- [ ] **Step 6:** Re-run the Phase 1 snatch timing check with `analyse_fps=10` to confirm detection still lands ≤ 10 s. If it doesn't, document the lowest safe `analyse_fps`.
- [ ] **Step 7: Commit** `feat(backend): scale test and analysis frame-rate control`.

---

### Task 3: Reports API and Results page

**Files:**
- Create: `backend/app/reports.py`, `backend/reports/baseline.json`; modify `backend/app/main.py`; create `frontend/src/app/results/page.tsx`, `frontend/src/components/KpiTile.tsx`, `LatencyBars.tsx`, `ScaleChart.tsx`; add the header nav link "Results"
- Test: `backend/tests/test_reports_api.py`, `frontend/src/app/results/page.test.tsx`

**Interfaces:**
- Produces:
  - `GET /api/reports` → `{benchmark: object|null, scale: object|null, baseline: object|null, generated_hint: string}`. It returns 200 even when files are missing (Review Focus 3), and `generated_hint` lists the commands to generate them.
  - `/results` page, in four sections:
    1. **KPI tiles:**
       - "Snatch → alert card" (`detection_to_card_p50_s`, shown next to the baseline `time_to_notice_s` or "baseline pending")
       - "Detected" (`event_recall_final` as %)
       - "False alarms reaching guard per hour" (`false_per_hour_final`)
       - "False alarms filtered by AI" (`ai_filter_rate` as %)
       - "Cameras per GPU" (`max_cameras_ok`)
    2. **Latency bars:** p50 and p90 per stage (detection, verification, push).
    3. **Scale chart:** fps per camera against the number of cameras, with the target-fps line and a marker for the last OK point.
    4. **Demo clips table:** expected vs result per demo clip.
  - A **warning banner** when `benchmark.meta.verifier == "mock"`: "Results use a mock AI verifier and are not valid evidence" (Review Focus 1).
  - A footer with the report metadata (commit, triggers, model, timestamp).

- [ ] **Step 1: Write the failing tests:**
  - backend: `test_reports_missing_files_returns_nulls`, `test_reports_returns_files_when_present`
  - frontend: `shows baseline pending when null`, `shows mock warning banner`, `renders KPI values from report`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Read the `dataviz` skill, then implement `reports.py`, the endpoint and the page in the CMS dark theme.
- [ ] **Step 4:** Run the backend and frontend tests. Expected: PASS.
- [ ] **Step 5:** Check `/results` manually with real report files.
- [ ] **Step 6: Commit** `feat: results page with benchmark and scale evidence`.

---

### Task 4: Guard feedback loop

**Files:**
- Create: `backend/scripts/export_feedback.py`
- Test: `backend/tests/test_export_feedback.py`

**Interfaces:**
- Consumes: `IncidentStore`, `read_labels`/`write_labels`, `LabelRow`, `load_cameras`
- Produces:
  - `export_feedback.py [--include-ai-rejected --confirm]`:
    - **Guard-REJECTED incidents:** append a `LabelRow(label="normal", origin="feedback", file=<clip copied to datasets/feedback/>, start=clip_start, end=clip_end, source_id="fb_<incident_id>", notes="guard rejected <date>")`.
    - **AI_REJECTED incidents**, only with `--include-ai-rejected`: interactive. With `--confirm`, it plays each clip segment with the `label_tool` player and asks `normal? [y/n/skip]`, then appends only the confirmed rows (Review Focus 5).
    - **Demo clips are skipped:** incidents whose clip is a demo clip are never exported, keeping the Phase 2 leakage rule. It prints "skipped N demo-clip incidents".
    - **Idempotent:** a row with `source_id == "fb_<incident_id>"` already present → skip (Review Focus 4).
    - It prints the count of appended rows and the reminder: "Re-run Phase 2 Tasks 2–4 to retrain with feedback."
- This is the "system learns from the guard" loop. The README and the Results page footer state the number of feedback rows collected.

- [ ] **Step 1: Write the failing tests:**
  - `test_export_appends_guard_rejected_as_normal`
  - `test_export_idempotent`
  - `test_export_skips_demo_clip_incidents`
  - `test_ai_rejected_not_exported_without_flag`
  - `test_ai_rejected_exported_only_when_confirmed` (inject the answers)
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `export_feedback.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5: Commit** `feat(training): guard feedback export to training labels`.

---

### Task 5: Demo freeze and rehearsal

**Files:**
- Modify: `README.md`, `backend/data/cameras.json` (final), `backend/reports/*.json` (final runs)

- [ ] **Step 1:** Run the full suites: `uv run pytest -v` in `backend/` and `npx vitest run` in `frontend/`. Expected: all PASS. Then `npm run build` in `frontend/`, which must succeed with no type errors.
- [ ] **Step 2:** Run the final benchmark with the real verifier (`--verifier claude`) and the final scale test. Regenerate the replay files.
- [ ] **Step 3:** Do a dress rehearsal three times, end to end, following the spec §4 script in **live** mode, then once in **replay** mode with Wi-Fi off (hotspot only for Twilio). Record any glitches in the README "Known issues" list.
- [ ] **Step 4:** Finish the README:
  - setup from a fresh clone
  - `.env` variables
  - live vs replay
  - pre-stage checklist (hotspot, verified Twilio numbers, volume, replay files fresh, `baseline.json` filled)
  - results tables (Phase 2 model metrics, benchmark, scale)
  - known issues
- [ ] **Step 5: Commit** `docs: final runbook and results`, then tag `git tag v1.0-demo`.
