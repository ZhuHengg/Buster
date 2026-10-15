import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Incident, IncidentStatus } from "@/lib/types";

import IncidentTable from "./IncidentTable";

function incident(id: string, status: IncidentStatus, over: Partial<Incident> = {}): Incident {
  return {
    id,
    camera_id: "CAM-02",
    status,
    candidate: {
      camera_id: "CAM-02", pts: 6.4, loop: 0, trigger: "rule", suspect_track_ids: [], victim_track_id: null,
      motorcycle_track_id: null, detected_at: "2026-10-11T04:05:00Z",
    },
    verification: null,
    verification_error: null,
    escape_direction: null,
    escape_exit: null,
    snapshot_files: [],
    clip_file: "case-2.mp4",
    clip_start: 2,
    clip_end: 9,
    guard_decision_at: null,
    operator: null,
    escalation: [],
    metrics: {},
    created_at: "2026-10-11T04:05:01Z",
    ...over,
  };
}

const verified = {
  is_incident: true, incident_type: "snatch_theft" as const, confidence: 0.9, summary: "x", suspects: [],
  victim: null, vehicle: null, escape_direction: "east" as const,
};

const sample = [
  incident("INC-1", "ESCALATED", {
    operator: "Aina",
    verification: verified,
    metrics: { candidate_s: 0.4, verified_s: 4.2, call_placed_s: 6.9 },
    created_at: "2026-10-11T04:05:01Z",
  }),
  incident("INC-2", "AI_REJECTED", {
    metrics: { candidate_s: 0.3, verified_s: 3.1 },
    created_at: "2026-10-11T04:06:01Z",
  }),
  incident("INC-3", "REJECTED", { operator: "Aina", created_at: "2026-10-11T04:07:01Z" }),
];

describe("IncidentTable", () => {
  it("renders status chips and metrics", () => {
    render(<IncidentTable incidents={sample} />);
    const rows = screen.getAllByRole("row").slice(1); // drop the header row
    expect(rows).toHaveLength(3);
    const escalated = rows.find((r) => within(r).queryByText("INC-1"))!;
    expect(within(escalated).getByText("Escalated")).toBeInTheDocument();
    expect(within(escalated).getByText("Aina")).toBeInTheDocument();
    expect(within(escalated).getByText("0.4 s")).toBeInTheDocument();
    expect(within(escalated).getByText("4.2 s")).toBeInTheDocument();
    expect(within(escalated).getByText("6.9 s")).toBeInTheDocument();
    expect(within(escalated).getByText(/Snatch theft/)).toBeInTheDocument();
    const aiRejected = rows.find((r) => within(r).queryByText("INC-2"))!;
    expect(within(aiRejected).getByText("AI rejected")).toBeInTheDocument();
    expect(within(aiRejected).getAllByText("—").length).toBeGreaterThanOrEqual(2); // no call metric, no operator
  });

  it("lists the newest incident first", () => {
    render(<IncidentTable incidents={sample} />);
    const ids = screen.getAllByRole("row").slice(1).map((r) => within(r).getByText(/^INC-\d$/).textContent);
    expect(ids).toEqual(["INC-3", "INC-2", "INC-1"]);
  });

  it("filters by status", async () => {
    render(<IncidentTable incidents={sample} />);
    await userEvent.click(screen.getByRole("button", { name: /AI rejected/ }));
    let rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(1);
    expect(within(rows[0]).getByText("INC-2")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^All/ }));
    rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
  });

  it("shows a count per filter and marks the active one", async () => {
    render(<IncidentTable incidents={sample} />);
    expect(screen.getByRole("button", { name: /^All 3/ })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: /Escalated 1/ }));
    expect(screen.getByRole("button", { name: /Escalated 1/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("calls onSelect with the clicked incident and highlights the selected row", async () => {
    const onSelect = vi.fn();
    render(<IncidentTable incidents={sample} selectedId="INC-2" onSelect={onSelect} />);
    await userEvent.click(screen.getByText("INC-1"));
    expect(onSelect).toHaveBeenCalledWith(sample[0]);
    const selected = screen.getAllByRole("row").find((r) => r.getAttribute("aria-selected") === "true")!;
    expect(within(selected).getByText("INC-2")).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    const { unmount } = render(<IncidentTable incidents={[]} />);
    expect(screen.getByText(/No incidents/)).toBeInTheDocument();
    unmount();
    const { rerender } = render(<IncidentTable incidents={sample} />);
    await userEvent.click(screen.getByRole("button", { name: /^Escalated/ }));
    rerender(<IncidentTable incidents={sample.filter((i) => i.status !== "ESCALATED")} />);
    expect(screen.getByText(/No incidents/)).toBeInTheDocument();
    // the selected filter stays on screen so it can be switched off
    expect(screen.getByRole("button", { name: /^Escalated/ })).toBeInTheDocument();
  });

  it("leaves out status filters that have no incidents", () => {
    render(<IncidentTable incidents={sample} />);
    expect(screen.getByRole("button", { name: /^Escalated/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Pending review/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Approved/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Candidate/ })).not.toBeInTheDocument();
  });

  describe("removing a log entry", () => {
    it("has no remove buttons unless the page can remove incidents", () => {
      render(<IncidentTable incidents={sample} />);
      expect(screen.queryByRole("button", { name: /^remove/i })).not.toBeInTheDocument();
    });

    it("asks to confirm, then removes only that incident", async () => {
      const onRemove = vi.fn();
      const onSelect = vi.fn();
      render(<IncidentTable incidents={sample} onRemove={onRemove} onSelect={onSelect} />);
      await userEvent.click(screen.getByRole("button", { name: "Remove INC-2" }));
      expect(onRemove).not.toHaveBeenCalled(); // one click is not enough
      expect(onSelect).not.toHaveBeenCalled(); // and it does not select the row
      await userEvent.click(screen.getByRole("button", { name: "Confirm remove INC-2" }));
      expect(onRemove).toHaveBeenCalledTimes(1);
      expect(onRemove).toHaveBeenCalledWith(sample[1]);
    });

    it("cancel keeps the incident", async () => {
      const onRemove = vi.fn();
      render(<IncidentTable incidents={sample} onRemove={onRemove} />);
      await userEvent.click(screen.getByRole("button", { name: "Remove INC-1" }));
      await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
      expect(onRemove).not.toHaveBeenCalled();
      expect(screen.getByRole("button", { name: "Remove INC-1" })).toBeInTheDocument();
    });

    it("only one row asks for confirmation at a time", async () => {
      render(<IncidentTable incidents={sample} onRemove={vi.fn()} />);
      await userEvent.click(screen.getByRole("button", { name: "Remove INC-1" }));
      await userEvent.click(screen.getByRole("button", { name: "Remove INC-2" }));
      expect(screen.getAllByRole("button", { name: /^confirm remove/i })).toHaveLength(1);
    });
  });
});
