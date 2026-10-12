import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ReportsResponse } from "@/lib/types";

const getReports = vi.fn();
vi.mock("@/lib/api", () => ({ getReports: () => getReports() }));

import ResultsPage from "./page";

const meta = (verifier: string) => ({
  commit: "e44cadd1234567", generated_at: "2026-10-12T05:00:00+00:00", triggers: "both", verifier,
  model: "claude-opus-5-5", screen_model: "gemini-2.5-flash", threshold: 0.6, sources: ["a.mp4"], clips: ["case-2.mp4"],
});

const aggregate = {
  sources: 10, events: 20, non_event_hours: 2.5, step1_hits: 19, final_hits: 18,
  event_recall_step1: 0.95, event_recall_final: 0.9, event_recall_final_ci95: [0.7, 0.97] as [number, number],
  step1_false: 10, final_false: 2, false_per_hour_step1: 4, false_per_hour_final: 0.8, ai_filter_rate: 0.8,
  verify_errors: 0, step1_wall_p50_s: 2.1, step1_wall_p90_s: 3.2, event_to_candidate_p50_s: 1.5,
  event_to_candidate_p90_s: 2.5, candidate_to_verified_p50_s: 4.2, candidate_to_verified_p90_s: 5.5, push_s: 0.3,
  detection_to_card_p50_s: 8.1, detection_to_card_p90_s: 10.3,
};

function reports(over: Partial<ReportsResponse> = {}): ReportsResponse {
  return {
    benchmark: {
      meta: meta("claude"),
      test: { aggregate, per_source: [] },
      demo: {
        per_clip: [
          { camera_id: "CAM-02", clip: "case-2.mp4", expected_event: { start: 5.4, end: 8.4 }, outcome: "detected", result: {} },
          { camera_id: "CAM-07", clip: "case-1.mp4", expected_event: null, outcome: "clean", result: {} },
        ],
      },
    },
    scale: {
      meta: { ...meta("dry-run"), gpu: "RTX 4070", analyse_fps: 10 },
      target_fps: 10,
      rows: [
        { n: 1, fps_mean: 10, fps_min: 10, lag_p90_s: 0.1, gpu_mem_gb: 1.1, ok: true },
        { n: 4, fps_mean: 9.8, fps_min: 9.5, lag_p90_s: 0.2, gpu_mem_gb: 2.4, ok: true },
        { n: 8, fps_mean: 5.1, fps_min: 4.9, lag_p90_s: 1.8, gpu_mem_gb: 4.4, ok: false },
      ],
      max_cameras_ok: 4,
      stopped_reason: "mean fps 5.1 < 0.9 x target 10 at N=8",
    },
    baseline: { time_to_notice_s: null, source: null },
    feedback_rows: 3,
    generated_hint: "uv run python scripts/benchmark.py --set both",
    ...over,
  };
}

async function show(r: ReportsResponse) {
  getReports.mockResolvedValue(r);
  render(<ResultsPage />);
  await screen.findByRole("heading", { name: /results/i });
}

// the KPI tile whose own label matches (the same words also appear in chart labels)
const tile = (label: RegExp) => {
  const found = screen.getAllByText(label).map((el) => el.closest("[data-kpi]")).find((el) => el !== null);
  if (!found) throw new Error(`no KPI tile for ${label}`);
  return found as HTMLElement;
};

beforeEach(() => {
  getReports.mockReset();
});

describe("Results page", () => {
  it("renders KPI values from the report", async () => {
    await show(reports());
    expect(within(tile(/snatch → alert card/i)).getByText("8.1 s")).toBeInTheDocument();
    expect(within(tile(/^detected$/i)).getByText("90%")).toBeInTheDocument();
    expect(within(tile(/false alarms reaching guard/i)).getByText("0.8")).toBeInTheDocument();
    expect(within(tile(/filtered by ai/i)).getByText("80%")).toBeInTheDocument();
    expect(within(tile(/cameras per gpu/i)).getByText("4")).toBeInTheDocument();
  });

  it("shows baseline pending when null", async () => {
    await show(reports());
    expect(within(tile(/snatch → alert card/i)).getByText(/baseline pending/i)).toBeInTheDocument();
  });

  it("shows the baseline number next to the result when it is filled in", async () => {
    await show(reports({ baseline: { time_to_notice_s: 120, source: "guard interviews, n=5" } }));
    const t = tile(/snatch → alert card/i);
    expect(within(t).getByText(/baseline 120 s/i)).toBeInTheDocument();
    expect(within(t).queryByText(/baseline pending/i)).not.toBeInTheDocument();
  });

  it("shows mock warning banner", async () => {
    const r = reports();
    r.benchmark!.meta = meta("mock");
    await show(r);
    expect(screen.getByRole("alert")).toHaveTextContent(/mock AI verifier and are not valid evidence/i);
  });

  it("has no warning banner for a real verifier", async () => {
    await show(reports());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("explains how to generate the reports when they are missing", async () => {
    await show(reports({ benchmark: null, scale: null }));
    expect(screen.getAllByText(/uv run python scripts\/benchmark\.py/i).length).toBeGreaterThan(0);
    expect(within(tile(/^detected$/i)).getByText("—")).toBeInTheDocument();
  });

  it("lists demo clips apart from the test set with expected vs result", async () => {
    await show(reports());
    const row = screen.getByRole("row", { name: /CAM-02/ });
    expect(within(row).getByText(/alert raised/i)).toBeInTheDocument();
    expect(within(row).getByText(/5\.4.*8\.4/)).toBeInTheDocument();
    const normal = screen.getByRole("row", { name: /CAM-07/ });
    expect(within(normal).getByText(/normal clip/i)).toBeInTheDocument();
  });

  it("shows the report metadata and feedback count in the footer", async () => {
    await show(reports());
    const footer = screen.getByRole("contentinfo");
    expect(footer).toHaveTextContent("e44cadd");
    expect(footer).toHaveTextContent("claude-opus-5-5");
    expect(footer).toHaveTextContent(/feedback rows: 3/i);
  });

  it("marks the last OK point and the stop on the scale chart", async () => {
    await show(reports());
    expect(screen.getByText(/4 cameras ok/i)).toBeInTheDocument();
    expect(screen.getByText(/mean fps 5\.1 < 0\.9 x target 10/i)).toBeInTheDocument();
  });

  it("tells the user when the API cannot be reached", async () => {
    getReports.mockRejectedValue(new Error("down"));
    render(<ResultsPage />);
    expect(await screen.findByText(/could not load reports/i)).toBeInTheDocument();
  });
});
