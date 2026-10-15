import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Incident } from "@/lib/types";

import IncidentLog from "./IncidentLog";

function inc(n: number, status: Incident["status"] = "PENDING_REVIEW"): Incident {
  return {
    id: `INC-0000${n}`,
    camera_id: "CAM-02",
    status,
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

const incidents = Object.fromEntries([inc(1), inc(2), inc(3), inc(4, "REJECTED")].map((i) => [i.id, i]));
const apply = vi.fn();
const approve = vi.fn();
const reject = vi.fn();

vi.mock("@/lib/cms", () => ({
  useCms: () => ({ state: { incidents }, removeIncident: () => undefined, applyIncident: apply }),
}));
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {
    status = 0;
  },
  getCameras: () => Promise.resolve([]),
  deleteIncident: () => Promise.resolve(),
  approve: (...a: unknown[]) => approve(...a),
  reject: (...a: unknown[]) => reject(...a),
  clipUrl: () => "",
  snapshotUrl: () => "",
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
});

const aside = () => screen.getByRole("complementary");

describe("Incident log decisions", () => {
  it("approves the selected pending incident", async () => {
    const user = userEvent.setup();
    approve.mockResolvedValue({ ...inc(3), status: "APPROVED" });
    render(<IncidentLog />);
    await user.click(screen.getByText("INC-00003"));
    await user.click(within(aside()).getByRole("button", { name: /approve/i }));
    expect(approve).toHaveBeenCalledWith("INC-00003", expect.any(String));
    expect(apply).toHaveBeenCalled();
  });

  it("Next pending walks the undecided incidents newest-first and wraps", async () => {
    const user = userEvent.setup();
    render(<IncidentLog />);
    await user.click(screen.getByText("INC-00003")); // newest pending
    const next = () => within(aside()).getByRole("button", { name: /next pending/i });
    expect(next()).toHaveTextContent("1 / 3");
    await user.click(next());
    expect(aside().textContent).toContain("INC-00002");
    await user.click(next());
    await user.click(next());
    expect(aside().textContent).toContain("INC-00003");
  });

  it("offers no decision buttons for an already decided incident", async () => {
    const user = userEvent.setup();
    render(<IncidentLog />);
    await user.click(screen.getByText("INC-00004"));
    expect(within(aside()).queryByRole("button", { name: /approve/i })).toBeNull();
    expect(within(aside()).getByRole("button", { name: /review next pending/i })).toBeInTheDocument();
  });
});
