# Proactive CCTV Alert System: Phase 2 Implementation Plan (Action Model)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train a video action model that tells motorcycle snatch theft from normal street activity, and plug it into the pipeline as a second Step 1 trigger. It fires alongside Rule B (either one can raise a candidate), so Step 1 misses fewer events.

**Architecture:** An offline training workspace in `backend/training/` turns raw videos into labelled segments, then into fixed 16-frame windows split by source video, then fine-tunes VideoMAE-base, then picks a threshold on the validation split and evaluates on the test split. The trained model is saved to `backend/models/action/`. At runtime, `ActionModelTrigger` implements the Phase 1 `Trigger` protocol on a sliding window of frames, and `AnyTrigger` combines it with `SnatchRule` under one shared cooldown.

**Tech Stack:** Phase 1 stack plus Hugging Face `transformers` (VideoMAE), `scikit-learn` (metrics), OpenCV (frame decoding, labelling tool).

**Spec:** `docs/SOLUTION_PLAN.md` §6.3 A and §7. **Depends on:** Phase 1 complete (`docs/superpowers/plans/2026-10-11-cctv-alert-phase1.md`), especially `Trigger`, `FrameDetections`, `CandidateEvent`, `Detector`, `SnatchRule`, `scripts/precompute.py`.

## Global Constraints

- All Phase 1 global constraints still apply (Python 3.12 via uv, Windows paths, no face recognition, nothing escalates without guard approval, zero-credential run).
- **Demo clips are never used for training, validation or testing selection.** Every clip referenced in `backend/data/cameras.json` is excluded automatically. The dataset build fails if one appears.
- **Split by source video, never by window.** No source video may contribute windows to more than one split.
- Window: **16 frames sampled evenly over 2.0 s**, resized to the shorter side 224 then centre-cropped to 224×224 (at inference, the crop follows Task 5's region rule).
- Model: `MCG-NJU/videomae-base-finetuned-kinetics`, with the head replaced for 2 labels `["normal", "snatch"]`. Fallback if VideoMAE won't train on the RTX 3080 (16 GB) at batch size ≥ 2 with fp16: torchvision `r2plus1d_18` (Kinetics weights). The spec names X3D-S, but that needs the unmaintained `pytorchvideo`; r2plus1d_18 is the substitute.
- Held-out targets (spec §7): **event recall ≥ 0.90** on test snatch events; **0 alerts after Step 2** on the normal demo clips (checked in Task 6).
- Runtime latency: the model trigger must keep Step 1 at **≤ 2 s** after the snatch, while YOLO runs on the same GPU.
- Datasets and models are git-ignored (`backend/data/datasets/`, `backend/data/windows/`, `backend/models/`). Only scripts, `labels.csv` and metrics JSON are committed.
- Online clips are for training and testing only. Respect platform terms; do not commit them.

## Review Focus

1. **Leakage between splits:** two downloads of the same viral video under different file names would inflate test results. The dataset build must flag near-duplicate sources by perceptual hash of the first frames. Test in Task 2.
2. **Label segments shorter than one window, or videos shorter than 2 s:** these must be skipped with a warning, not crash the build or produce padded garbage windows. Test in Task 2.
3. **Class imbalance:** normal footage will outnumber snatch windows about 10:1. Training must weight classes, and evaluation must report per-class numbers, not just accuracy. Test in Task 3 and Task 4.
4. **GPU contention at runtime:** if the model inference falls behind real time, it must drop old windows rather than queue them. Stale alerts minutes late are worse than none. Test in Task 5.
5. **Both triggers fire for the same event:** this must create exactly one candidate, with the shared cooldown applied. Test in Task 5.

---

## File Structure

```
backend/
  training/
    __init__.py
    labels.py           LabelRow model, read/write labels.csv, validation
    label_tool.py       OpenCV labelling tool (CLI)
    ingest.py           register raw videos into labels.csv (origin, source_id, hash)
    windows.py          window sampling + preprocessing (shared by training AND runtime)
    build_dataset.py    labels → split → windows/*.npy + index.parquet/csv
    dataset.py          torch Dataset over windows + augmentations
    train.py            fine-tune loop (VideoMAE or r2plus1d_18)
    evaluate.py         window + event metrics, threshold selection
  app/trigger/action_model.py   ActionModelTrigger
  app/trigger/any_trigger.py    AnyTrigger
  data/labels.csv               committed
  models/action/                model files + threshold.json + metrics.json (git-ignored except the JSON)
  tests/training/...            tests for labels, windows, build_dataset, evaluate
  tests/trigger/test_action_model.py, test_any_trigger.py
docs/FILMING_GUIDE.md           shot list for the staged clips
```

---

### Task 1: Labels format, ingest, labelling tool, filming guide

**Files:**
- Create: `backend/training/__init__.py`, `backend/training/labels.py`, `backend/training/ingest.py`, `backend/training/label_tool.py`, `docs/FILMING_GUIDE.md`; modify `backend/pyproject.toml` (add `transformers`, `scikit-learn` to the main dependencies)
- Test: `backend/tests/training/test_labels.py`, `backend/tests/training/test_ingest.py`

**Interfaces:**
- Produces:
  - `LabelRow` (pydantic) with fields:
    - `source_id: str` (stable ID of the original video, e.g. `ucf_Robbery012`, `yt_<hash8>`, `staged_take07`)
    - `file: str` (path relative to `backend/data/datasets/`)
    - `start: float` and `end: float` (seconds; `end > start`)
    - `label: Literal["snatch","normal"]`
    - `origin: Literal["ucf","online","staged","feedback"]`
    - `angle: Literal["high","eye","unknown"]`
    - `light: Literal["day","dusk","night","unknown"]`
    - `phash: str` (perceptual hash of the first frames)
    - `notes: str = ""`
  - `read_labels(path) -> list[LabelRow]` and `write_labels(path, rows)`; `validate_labels(rows) -> list[str]` (error messages for overlapping segments of the same file with different labels, `end > video duration`, unknown files)
  - `ingest.py <folder> --origin <origin> [--angle] [--light]`: registers every video in the folder by adding a whole-video `normal` row if the folder name contains `normal`, otherwise only computing `source_id` and `phash` and printing "needs labelling". It never overwrites existing rows.
  - `label_tool.py <file>`: an OpenCV player. Space pauses, `,` and `.` step a frame, `j`/`l` jump ±2 s, `[` and `]` set start and end, `s` saves a `snatch` row, `n` saves a `normal` row, `q` quits. It shows the current time and the existing segments as a coloured bar.
- `docs/FILMING_GUIDE.md`: the shot list from spec §12. At least 15 snatch takes from 2–3 high fixed angles (day and dusk) and at least 10 normal takes at the same spots; the phone mounted at ≥ 2.5 m pointing down, 1080p 30 fps, landscape. Safety and permission rules: private ground or owner permission, guards warned, slow riding, fake bag, consenting actors. Record which image direction leads to which gate. File naming: `staged_<spot>_<take>_<snatch|normal>.mp4`.

- [ ] **Step 1: Write the failing tests:**
  - `test_label_row_rejects_end_before_start`
  - `test_validate_flags_conflicting_overlap`
  - `test_validate_flags_end_beyond_duration` (uses a synthetic 1 s video)
  - `test_ingest_adds_normal_rows_for_normal_folder`
  - `test_ingest_does_not_duplicate_existing_source`
- [ ] **Step 2:** Run `uv run pytest tests/training -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `labels.py` and `ingest.py`. Implement the perceptual hash as a 64-bit difference hash (dHash) in numpy on 3 frames at 10/50/90% of the clip (grayscale, resized to 9×8), concatenated into a 192-bit hex string; Hamming distance is summed over the three. Do not add `opencv-contrib-python`, because it conflicts with `opencv-python`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Implement `label_tool.py`. Check it manually on `case-1.mp4` copied to a temp folder (not in `datasets/`): mark one segment and confirm a row appears in a scratch CSV.
- [ ] **Step 6:** Write `docs/FILMING_GUIDE.md`.
- [ ] **Step 7: Commit** `feat(training): labels format, ingest, labelling tool, filming guide`.

**Human step (the user, not the agent):** download the UCF-Crime Robbery, Stealing and part of the Normal videos into `backend/data/datasets/ucf_crime/{Robbery,Stealing,Normal_subset}/`, put online clips in `backend/data/datasets/online/{snatch,normal}/` (search keywords are in spec §10), and film the staged clips per the guide into `backend/data/datasets/staged/`. Then run `ingest.py` on each folder and use `label_tool.py` to mark the snatch segments. **Minimum to proceed to Task 3:** 60 snatch segments from ≥ 40 distinct sources, plus ≥ 2 hours of normal footage.

---

### Task 2: Window sampling and dataset build

**Files:**
- Create: `backend/training/windows.py`, `backend/training/build_dataset.py`
- Test: `backend/tests/training/test_windows.py`, `backend/tests/training/test_build_dataset.py`

**Interfaces:**
- Consumes: `LabelRow`, `read_labels`, `load_cameras` (Phase 1)
- Produces:
  - `sample_indices(start_s, fps, n=16, span_s=2.0) -> list[int]`: evenly spaced frame indices
  - `preprocess(frames: list[np.ndarray], size=224, crop: tuple[int,int,int,int] | None = None) -> np.ndarray` (uint8 `[16,224,224,3]`, RGB). If `crop` is given, crop to it first (it is expanded to a square by padding with edge pixels); then resize the shorter side to 224 and centre-crop.
  - `read_window(path, start_s, ...) -> np.ndarray | None`, which returns None if the video is shorter than needed (Review Focus 2)
  - **These functions are the single source of preprocessing for both training and runtime.**
  - `build_dataset.py --labels data/labels.csv --out data/windows/ [--stride-pos 0.25] [--stride-neg 1.0] [--seed 42]`:
    1. Excludes every clip in `cameras.json`; raises an error if any labelled `file` matches a demo clip by name **or by phash** (Hamming distance ≤ 6).
    2. Groups sources whose phash is within distance ≤ 6 into one group (near-duplicates; Review Focus 1).
    3. Splits groups 70/15/15 into train/val/test, stratified so that each split has snatch sources (`StratifiedGroupKFold`-style logic or a manual greedy split).
    4. Positive windows: windows overlapping a snatch segment by ≥ 50%, with stride `stride-pos`.
    5. Negative windows: from normal segments, plus **hard negatives** from the non-snatch parts of snatch videos (≥ 2 s away from the segment), with stride `stride-neg`.
    6. Writes each window as `windows/<split>/<label>/<source_id>_<start_ms>.npy` plus an `index.csv` (`path, split, label, source_id, origin, start`).
    7. Prints counts per split, label and origin.

- [ ] **Step 1: Write the failing tests:**
  - `test_sample_indices_even_spacing`
  - `test_preprocess_shape_and_dtype`
  - `test_preprocess_with_crop_pads_to_square`
  - `test_read_window_short_video_returns_none`
  - `test_build_excludes_demo_clip_by_name_and_phash`
  - `test_build_near_duplicates_same_split`
  - `test_build_no_source_in_two_splits`
  - `test_build_hard_negatives_away_from_segment`
  - `test_build_skips_segment_shorter_than_window_with_warning`

  The build tests use 4–6 synthetic videos written into `tmp_path`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `windows.py` and `build_dataset.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Run the real build: `uv run python -m training.build_dataset --labels data/labels.csv --out data/windows`. Expected: no errors, and every split has ≥ 1 snatch source. Record the counts in `backend/models/action/dataset_stats.json`.
- [ ] **Step 6: Commit** `feat(training): window sampling and leak-safe dataset build`.

---

### Task 3: Training

**Files:**
- Create: `backend/training/dataset.py`, `backend/training/train.py`
- Test: `backend/tests/training/test_dataset.py`, `backend/tests/training/test_train_smoke.py`

**Interfaces:**
- Consumes: the `index.csv` and windows from Task 2
- Produces:
  - `WindowDataset(index_csv, split, augment: bool)`: returns `(tensor [16,3,224,224] float normalised with the VideoMAE image processor mean/std, label int)`. Augmentations when `augment`, applied identically across all 16 frames of a window:
    - horizontal flip (p = 0.5)
    - brightness and contrast ±25%
    - Gaussian blur (p = 0.2)
    - JPEG re-compression at quality 30–70 (p = 0.3)
    - random resized crop with scale 0.8–1.0
  - `class_weights(index_csv, split="train") -> torch.Tensor` (inverse frequency, normalised)
  - `train.py --arch videomae|r2plus1d --epochs 15 --batch 4 --accum 4 --lr 5e-5 --out models/action/ [--max-steps N]`:
    - uses AdamW, cosine schedule with 10% warmup, fp16 autocast, and weighted cross-entropy
    - evaluates on the val split each epoch, keeping the best val **snatch F1**, with early stopping patience 4
    - saves `model/` (`save_pretrained` for VideoMAE, a `state_dict` + `arch.json` for r2plus1d), `train_log.csv` and `labels.json` (`["normal","snatch"]`)
- **The class order `["normal","snatch"]` is fixed everywhere.**

- [ ] **Step 1: Write the failing tests:**
  - `test_dataset_item_shape_and_label`
  - `test_augment_same_flip_for_all_frames`
  - `test_class_weights_favour_minority` (Review Focus 3)
  - `test_train_smoke_runs_two_steps`, which runs `train.py --arch r2plus1d --max-steps 2 --batch 2` on a tiny synthetic windows folder on CPU and asserts the output files exist
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `dataset.py` and `train.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Run the real training: `uv run python -m training.train --arch videomae --out models/action/`. If it runs out of memory at batch 4, retry at `--batch 2 --accum 8`; if it still fails, use `--arch r2plus1d`. Record which architecture was used in `models/action/arch.json`.
- [ ] **Step 6: Commit** `feat(training): action model fine-tuning` (code and `train_log.csv` only, not weights).

---

### Task 4: Evaluation and threshold selection

**Files:**
- Create: `backend/training/evaluate.py`
- Test: `backend/tests/training/test_evaluate.py`

**Interfaces:**
- Consumes: the trained model folder, the windows `index.csv`, and `labels.csv` (for event-level evaluation on the full test videos)
- Produces:
  - `event_hits(scores: list[tuple[float,float]], events: list[tuple[float,float]], threshold, consecutive=2, tolerance_s=1.5) -> tuple[int, int]` (hits, false triggers). `scores` are `(window_start_s, p_snatch)` pairs with 0.5 s stride. A trigger is ≥ `consecutive` consecutive windows ≥ threshold. It is a hit if it falls within `[event.start - tolerance, event.end + tolerance]`; otherwise it is a false trigger. Merge triggers within the 10 s cooldown.
  - `choose_threshold(val_results, max_false_per_hour=2.0) -> float`: the lowest threshold whose false triggers per hour of normal footage are ≤ the limit; among those, the one with the highest event recall
  - `evaluate.py --model models/action/ --split val|test`:
    - scores every val/test **source video end to end** with a 0.5 s stride
    - writes `models/action/metrics_<split>.json` with: window precision/recall/F1 per class, the confusion matrix, event recall, false triggers per hour, the threshold, and the number of events and hours
    - with `--split val`, also writes `threshold.json`
- **Report per-class numbers, never plain accuracy alone** (Review Focus 3).

- [ ] **Step 1: Write the failing tests:**
  - `test_event_hits_counts_hit_within_tolerance`
  - `test_event_hits_single_window_below_consecutive_not_trigger`
  - `test_event_hits_merges_within_cooldown`
  - `test_choose_threshold_respects_false_rate`
  - `test_choose_threshold_prefers_recall`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `evaluate.py`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Run `--split val` (which writes the threshold), then `--split test`. Target: **event recall ≥ 0.90** on test. If it falls short, add data (more staged takes, or the hard negatives from the false triggers) and repeat Tasks 2–4. Record each round in `models/action/ROUNDS.md` (data counts, architecture, val/test metrics).
- [ ] **Step 6: Commit** `feat(training): event-level evaluation and threshold selection` (with the metrics JSON).

---

### Task 5: Runtime trigger and combination with Rule B

**Files:**
- Create: `backend/app/trigger/action_model.py`, `backend/app/trigger/any_trigger.py`; modify `backend/app/config.py` (add `triggers: Literal["rule","model","both"] = "both"`, `action_model_dir: Path = backend/models/action`), `backend/app/main.py` and `backend/scripts/precompute.py` (build triggers via `make_trigger`)
- Test: `backend/tests/trigger/test_action_model.py`, `backend/tests/trigger/test_any_trigger.py`

**Interfaces:**
- Consumes: the `Trigger` protocol (`update(fd, frame)`, `reset()`), `CandidateEvent`, `windows.preprocess`, `sample_indices` logic, the model folder, `threshold.json`
- Produces:
  - `ActionModelTrigger(model_dir: Path, device="cuda:0", stride_s=0.5, consecutive=2, cooldown_s=10.0, max_lag_s=1.0)`:
    - keeps a 2.2 s ring buffer of `(pts, frame, fd)`
    - every `stride_s` of pts, it picks 16 frames over the last 2.0 s and computes the **crop region**: the union bbox of all motorcycles and persons within 1.5 × the pedestrian height of any motorcycle in the window, padded by 25%, or the full frame if there are none
    - it preprocesses with `windows.preprocess`, runs the model in a **single background worker thread**, and fires after `consecutive` scores ≥ threshold
    - `suspect_track_ids` are the riders of the motorcycle closest to a pedestrian at the trigger pts (same rider/pedestrian classification as `SnatchRule`, so import the helper instead of copying it)
    - **If a result returns with pts older than `max_lag_s` behind the latest frame, it is discarded, and windows queued while the worker is busy are dropped (keep only the newest)** (Review Focus 4)
    - `reset()` clears the buffer, the scores and the cooldown
  - `AnyTrigger(triggers: list[Trigger], cooldown_s=10.0)`: calls every trigger each frame and returns the first candidate. Once a candidate has been emitted, further candidates from **any** trigger are suppressed for `cooldown_s` (Review Focus 5). `reset()` resets all of them.
  - `make_trigger(settings) -> Trigger`: `rule` → `SnatchRule`; `model` → `ActionModelTrigger`; `both` → `AnyTrigger([SnatchRule, ActionModelTrigger])`. If the model folder or `threshold.json` is missing, it logs a warning and falls back to the rule only.
- Move the rider/pedestrian classification helper from `snatch_rule.py` into `app/trigger/scene.py` with the signature `classify_persons(fd: FrameDetections) -> tuple[dict[int,int], list[int]]` (rider track → motorcycle track, pedestrian track IDs). `SnatchRule` imports it from there; its existing tests must still pass.

- [ ] **Step 1: Write the failing tests** (they use a fake model callable injected via a `scorer` parameter for testability: `ActionModelTrigger(..., scorer: Callable[[np.ndarray], float] | None = None)`):
  - `test_fires_after_two_consecutive_high_scores`
  - `test_single_high_score_does_not_fire`
  - `test_crop_region_covers_motorcycle_and_nearby_pedestrian`
  - `test_crop_full_frame_when_no_motorcycle`
  - `test_stale_result_discarded_when_lagging` (the fake scorer sleeps longer than `max_lag_s`)
  - `test_busy_worker_keeps_only_newest_window`
  - `test_reset_clears_state_on_loop`
  - `test_any_trigger_one_candidate_when_both_fire`
  - `test_any_trigger_cooldown_applies_across_triggers`
  - `test_make_trigger_falls_back_to_rule_without_model`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement `scene.py`, `action_model.py` and `any_trigger.py`, and wire up `make_trigger`.
- [ ] **Step 4:** Run the full suite with `uv run pytest -v`. Expected: all PASS, including the Phase 1 tests.
- [ ] **Step 5: Measure latency.** Write `scripts/debug_trigger.py <clip> --triggers both`, which prints each candidate's trigger source and the delay between the labelled snatch time and the candidate. Expected: ≤ 2 s on the snatch demo clip, and no candidate on the normal clip.
- [ ] **Step 6: Commit** `feat(backend): action model trigger combined with Rule B`.

---

### Task 6: Regression on the demo and refreshed replay

**Files:**
- Modify: `README.md` (results section), `backend/data/precomputed/*` (regenerated, git-ignored)

- [ ] **Step 1:** Regenerate the replay files with `scripts/precompute.py` for each analysed camera, using `TRIGGERS=both`.
- [ ] **Step 2:** Repeat the Phase 1 Task 14 checks: snatch → card ≤ 10 s over 3 runs; the normal clip looping for 10 minutes gives 0 PENDING_REVIEW. Also record how many candidates came from `rule` vs `model`, and how many Step 2 rejected (from `/incidents`).
- [ ] **Step 3:** Update the README results with the model metrics (test event recall, false triggers per hour) and the demo checks.
- [ ] **Step 4: Commit** `docs: phase 2 results`.
