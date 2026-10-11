import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CameraConfig, EscalationStep, Incident, VerificationResult } from "@/lib/types";

import AlertCard from "./AlertCard";
import EscalationTimeline from "./EscalationTimeline";

const camera: CameraConfig = {
  id: "CAM-02", name: "Elmina Shoplot Row B", location: "Jalan Limau Manis", clip: "case-2.mp4",
  analyse: true, exits: { right: "Gate B" }, compass: { right: "east" }, sync: null,
};

const verification: VerificationResult = {
  is_incident: true,
  incident_type: "snatch_theft",
  confidence: 0.93,
  summary: "A rider on a black motorcycle snatched a bag from a woman and fled east.",
  suspects: [{ track_id: 16, description: "rider in white shirt and dark helmet" }],
  victim: { track_id: 1, description: "woman in pink top" },
  vehicle: { type: "motorcycle", colour: "black", plate_visible: false, plate_text: null },
  escape_direction: "east",
};

function makeIncident(over: Partial<Incident> = {}): Incident {
  return {
    id: "INC-20261011-0001",
    camera_id: "CAM-02",
    status: "PENDING_REVIEW",
    candidate: {
      camera_id: "CAM-02", pts: 6.4, loop: 0, trigger: "rule", suspect_track_ids: [16],
      victim_track_id: 1, motorcycle_track_id: 18, detected_at: "2026-10-11T04:05:00Z",
    },
    verification,
    verification_error: null,
    escape_direction: "east",
    escape_exit: "Gate B",
    snapshot_files: ["INC-20261011-0001_16.jpg"],
    clip_file: "case-2.mp4",
    clip_start: 2.4,
    clip_end: 9.4,
    guard_decision_at: null,
    operator: null,
    escalation: [],
    metrics: {},
    created_at: "2026-10-11T04:05:01Z",
    ...over,
  };
}

const step = (channel: EscalationStep["channel"], status: EscalationStep["status"]): EscalationStep => ({
  channel, status, detail: null, updated_at: "2026-10-11T04:05:10Z",
});

const noop = () => undefined;

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
});

describe("AlertCard", () => {
  it("renders summary, exit and confidence", () => {
    render(<AlertCard incident={makeIncident()} camera={camera} onApprove={noop} onReject={noop} busy={false} />);
    expect(screen.getByText(/snatched a bag from a woman/)).toBeInTheDocument();
    expect(screen.getByText(/Gate B/)).toBeInTheDocument();
    expect(screen.getByText(/East/)).toBeInTheDocument(); // escape row: "East → Gate B"
    expect(screen.getByText("93%")).toBeInTheDocument();
    expect(screen.getByText(/CAM-02/)).toBeInTheDocument();
    expect(screen.getByText(/Jalan Limau Manis/)).toBeInTheDocument();
    expect(screen.getByText(/dark helmet/)).toBeInTheDocument();
    expect(screen.getAllByText(/black motorcycle/).length).toBeGreaterThanOrEqual(1); // summary and vehicle row
  });

  it("shows the replay clip limited to the incident window and the snapshots", () => {
    const { container } = render(
      <AlertCard incident={makeIncident()} camera={camera} onApprove={noop} onReject={noop} busy={false} />,
    );
    const video = container.querySelector("video")!;
    expect(video.getAttribute("src")).toMatch(/\/media\/clips\/case-2\.mp4#t=2\.4,9\.4$/);
    const img = screen.getByAltText(/suspect snapshot/i);
    expect(img.getAttribute("src")).toMatch(/\/media\/snapshots\/INC-20261011-0001_16\.jpg$/);
  });

  it("loops the replay back to the clip start after clip_end", () => {
    const { container } = render(
      <AlertCard incident={makeIncident()} camera={camera} onApprove={noop} onReject={noop} busy={false} />,
    );
    const video = container.querySelector("video")!;
    video.currentTime = 9.5;
    video.dispatchEvent(new Event("timeupdate"));
    expect(video.currentTime).toBeCloseTo(2.4);
  });

  it("shows unverified badge when verification is null", () => {
    const incident = makeIncident({ verification: null, verification_error: "AI verification unavailable: timed out" });
    render(<AlertCard incident={incident} camera={camera} onApprove={noop} onReject={noop} busy={false} />);
    expect(screen.getByText("AI verification unavailable: operator to confirm")).toBeInTheDocument();
    expect(screen.getByAltText(/suspect snapshot/i)).toBeInTheDocument(); // still shows evidence
    expect(screen.getByRole("button", { name: /approve & escalate/i })).toBeEnabled();
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
  });

  it("does not show the unverified badge for a verified incident", () => {
    render(<AlertCard incident={makeIncident()} camera={camera} onApprove={noop} onReject={noop} busy={false} />);
    expect(screen.queryByText(/AI verification unavailable/)).not.toBeInTheDocument();
  });

  it("buttons disabled while busy", () => {
    render(<AlertCard incident={makeIncident()} camera={camera} onApprove={noop} onReject={noop} busy />);
    expect(screen.getByRole("button", { name: /approve & escalate/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /reject/i })).toBeDisabled();
  });

  it("approve calls onApprove once even on double click", async () => {
    const onApprove = vi.fn();
    render(<AlertCard incident={makeIncident()} camera={camera} onApprove={onApprove} onReject={noop} busy={false} />);
    await userEvent.dblClick(screen.getByRole("button", { name: /approve & escalate/i }));
    expect(onApprove).toHaveBeenCalledTimes(1);
  });

  it("reject calls onReject once", async () => {
    const onReject = vi.fn();
    render(<AlertCard incident={makeIncident()} camera={camera} onApprove={noop} onReject={onReject} busy={false} />);
    await userEvent.click(screen.getByRole("button", { name: /reject \(false positive\)/i }));
    expect(onReject).toHaveBeenCalledTimes(1);
  });

  it("allows another attempt after a failed request (busy true then false while still pending)", async () => {
    const onApprove = vi.fn();
    const props = { incident: makeIncident(), camera, onApprove, onReject: noop };
    const { rerender } = render(<AlertCard {...props} busy={false} />);
    await userEvent.click(screen.getByRole("button", { name: /approve & escalate/i }));
    rerender(<AlertCard {...props} busy />);
    rerender(<AlertCard {...props} busy={false} />);
    await userEvent.click(screen.getByRole("button", { name: /approve & escalate/i }));
    expect(onApprove).toHaveBeenCalledTimes(2);
  });

  it("plays the alert sound once per new pending incident", () => {
    const calls = () => vi.mocked(HTMLMediaElement.prototype.play).mock.calls.length;
    const before = calls();
    const props = { camera, onApprove: noop, onReject: noop, busy: false };
    const { rerender } = render(<AlertCard incident={makeIncident()} {...props} />);
    expect(calls()).toBe(before + 1);
    rerender(<AlertCard incident={makeIncident({ metrics: { shown_s: 3 } })} {...props} />);
    expect(calls()).toBe(before + 1); // same incident: no second tone
    rerender(<AlertCard incident={makeIncident({ id: "INC-20261011-0002" })} {...props} />);
    expect(calls()).toBeGreaterThanOrEqual(before + 2); // a new incident rings again
  });

  it("after approval shows the escalation timeline instead of the buttons", () => {
    const incident = makeIncident({ status: "ESCALATED", escalation: [step("police_call", "ringing")] });
    render(<AlertCard incident={incident} camera={camera} onApprove={noop} onReject={noop} busy={false} />);
    expect(screen.queryByRole("button", { name: /approve & escalate/i })).not.toBeInTheDocument();
    expect(screen.getByText("Police call")).toBeInTheDocument();
    expect(screen.getByText(/Ringing/)).toBeInTheDocument();
  });
});

describe("EscalationTimeline", () => {
  it("shows police call, police SMS and gate rows with their state", () => {
    render(
      <EscalationTimeline
        gateLabel="Gate B"
        steps={[step("police_call", "completed"), step("police_sms", "sent"), step("gate_sms", "failed")]}
      />,
    );
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText("Police call")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Completed")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Police SMS")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Sent")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Gate B alert")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Failed")).toBeInTheDocument();
  });

  it("shows pending rows before any step arrives, and skipped steps", () => {
    render(<EscalationTimeline steps={[step("gate_sms", "skipped")]} />);
    const rows = screen.getAllByRole("listitem");
    expect(within(rows[0]).getByText("Waiting")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Skipped")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Gate alert")).toBeInTheDocument();
  });
});
