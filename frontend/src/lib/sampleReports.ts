import type { ReportsResponse } from "./types";

/**
 * Demo figures for the Analysis page, used wherever the backend has no real benchmark / scale report
 * yet. They are illustrative, not measured: replace them by running the benchmark scripts.
 */
export const SAMPLE_REPORTS: ReportsResponse = {
  benchmark: {
    meta: {
      commit: "demo000",
      generated_at: "2026-10-12T03:10:00Z",
      triggers: "rule",
      verifier: "demo",
      model: "demo",
      threshold: 0.6,
      sources: ["demo"],
      clips: [],
    },
    test: {
      aggregate: {
        sources: 14,
        events: 24,
        non_event_hours: 6.5,
        event_recall_step1: 0.96,
        event_recall_final: 0.92,
        event_recall_final_ci95: [0.74, 0.98],
        false_per_hour_step1: 7.4,
        false_per_hour_final: 1.2,
        ai_filter_rate: 0.84,
        verify_errors: 0,
        event_to_candidate_p50_s: 2.1,
        event_to_candidate_p90_s: 3.4,
        step1_wall_p50_s: 0.6,
        step1_wall_p90_s: 1.1,
        candidate_to_verified_p50_s: 6.2,
        candidate_to_verified_p90_s: 10.1,
        push_s: 0.2,
        detection_to_card_p50_s: 9.0,
        detection_to_card_p90_s: 14.6,
      },
      per_source: [],
    },
    demo: {
      per_clip: [
        { camera_id: "CAM-01", clip: "case-1.mp4", expected_event: null, outcome: "clean", result: {} },
        { camera_id: "CAM-02", clip: "case-2.mp4", expected_event: { start: 6, end: 14 }, outcome: "detected", result: {} },
        { camera_id: "CAM-03", clip: "case-3.mp4", expected_event: null, outcome: "filtered_by_ai", result: {} },
        { camera_id: "CAM-04", clip: "case-4.mp4", expected_event: { start: 3, end: 9 }, outcome: "detected", result: {} },
        { camera_id: "CAM-05", clip: "case-5.mp4", expected_event: null, outcome: "false_alarm", result: {} },
        { camera_id: "CAM-07", clip: "case-7.mp4", expected_event: { start: 12, end: 20 }, outcome: "missed", result: {} },
      ],
    },
  },
  scale: {
    meta: {
      commit: "demo000",
      generated_at: "2026-10-12T03:12:00Z",
      triggers: "rule",
      verifier: "demo",
      model: null,
      threshold: null,
      sources: [],
      clips: [],
      gpu: "NVIDIA GeForce RTX 3080 Laptop GPU",
      analyse_fps: 10,
    },
    target_fps: 10,
    max_cameras_ok: 5,
    stopped_reason: "Stopped at 7 cameras: GPU memory ran out.",
    rows: [
      { n: 1, fps_mean: 10.0, fps_min: 9.9, lag_p90_s: 0.1, gpu_mem_gb: 1.8, ok: true },
      { n: 2, fps_mean: 9.9, fps_min: 9.7, lag_p90_s: 0.2, gpu_mem_gb: 2.4, ok: true },
      { n: 3, fps_mean: 9.8, fps_min: 9.5, lag_p90_s: 0.3, gpu_mem_gb: 3.0, ok: true },
      { n: 4, fps_mean: 9.6, fps_min: 9.2, lag_p90_s: 0.4, gpu_mem_gb: 3.6, ok: true },
      { n: 5, fps_mean: 9.2, fps_min: 8.8, lag_p90_s: 0.7, gpu_mem_gb: 4.2, ok: true },
      { n: 6, fps_mean: 7.4, fps_min: 6.1, lag_p90_s: 2.3, gpu_mem_gb: 4.8, ok: false },
      { n: 7, fps_mean: null, fps_min: null, lag_p90_s: null, gpu_mem_gb: null, ok: false, oom: true, error: "out of memory" },
    ],
  },
  baseline: { time_to_notice_s: 62, source: "manual monitoring" },
  feedback_rows: 0,
  generated_hint: "",
};
