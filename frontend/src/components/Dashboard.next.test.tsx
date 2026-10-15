import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CameraConfig, Incident } from "@/lib/types";

import Dashboard from "./Dashboard";

const cameras: CameraConfig[] = [
  { id: "CAM-02", name: "Row B", location: "Elmina", clip: "case-2.mp4", analyse: true, exits: {}, compass: {}, sync: null },
];

function inc(n: number): Incident {
  const id = `INC-0000${n}`;
  return {
    id,
    camera_id: "CAM-02",
    status: "PENDING_REVIEW",
    candidate: {
      camera_id: "CAM-02", pts: 1, loop: 0, trigger: "rule", suspect_track_ids: [], victim_track_id: null,
      motorcycle_track_id: null, detected_at: `2026-10-11T04:0${n}:00Z`,
    },
    verification: null,
    verification_error: null,
    escape_direction: null,
    escape_exit: null,
    snapshot_files: [],
    clip_file: "case-2.mp4",
    clip_start: 0,
    clip_end: 1,
    guard_decision_at: null,
    operator: null,
    escalation: [],
    metrics: {},
    created_at: `2026-10-11T04:0${n}:01Z`,
  };
}

const incidents = Object.fromEntries([1, 2, 3].map((n) => [inc(n).id, inc(n)]));

vi.mock("@/lib/cms", () => ({
  useCms: () => ({
    state: { incidents, activeAlertId: "INC-00001", detections: {}, sync: {}, playback: { paused: false, loop: true } },
    connected: true,
    cameras,
    cameraLoadFailures: 0,
    applyIncident: () => undefined,
    streams: {},
    reportStream: () => undefined,
  }),
}));
vi.mock("./CameraGrid", () => ({ default: () => null }));

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
});

describe("Dashboard next alert", () => {
  it("Next cycles through pending alerts and wraps", async () => {
    const user = userEvent.setup();
    render(<Dashboard />);
    const shown = () => screen.getByLabelText("Security alert").textContent;
    expect(shown()).toContain("INC-00001");
    expect(screen.getByRole("button", { name: /next alert/i })).toHaveTextContent("1 / 3");
    await user.click(screen.getByRole("button", { name: /next alert/i }));
    expect(shown()).toContain("INC-00002");
    await user.click(screen.getByRole("button", { name: /next alert/i }));
    expect(shown()).toContain("INC-00003");
    expect(screen.getByRole("button", { name: /next alert/i })).toHaveTextContent("3 / 3");
    await user.click(screen.getByRole("button", { name: /next alert/i }));
    expect(shown()).toContain("INC-00001");
  });

  it("× only hides the panel; it never switches to another alert", async () => {
    const user = userEvent.setup();
    render(<Dashboard />);
    await user.click(screen.getByRole("button", { name: /next alert/i })); // now on INC-00002
    await user.click(screen.getByRole("button", { name: /close alert/i }));
    expect(screen.queryByLabelText("Security alert")).toBeNull();
    // reopening brings back the same alert, and Next still walks all of them
    await user.click(screen.getByRole("button", { name: /awaiting review/i }));
    expect(screen.getByLabelText("Security alert").textContent).toContain("INC-00002");
    expect(screen.getByRole("button", { name: /next alert/i })).toHaveTextContent("2 / 3");
  });
});
