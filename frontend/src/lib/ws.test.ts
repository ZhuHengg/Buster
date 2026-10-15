import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DetectionsMsg, Incident, IncidentStatus } from "./types";
import { cmsReducer, initialCmsState, useCmsSocket } from "./ws";

vi.mock("./api", () => ({
  API_BASE: "http://localhost:8000",
  wsUrl: () => "ws://localhost:8000/ws",
  getIncidents: vi.fn(),
  getPlayback: vi.fn(),
}));
import { getIncidents, getPlayback } from "./api";

function incident(id: string, status: IncidentStatus, created = "2026-10-11T04:00:00Z"): Incident {
  return {
    id,
    camera_id: "CAM-02",
    status,
    candidate: {
      camera_id: "CAM-02", pts: 6, loop: 0, trigger: "rule", suspect_track_ids: [3],
      victim_track_id: 1, motorcycle_track_id: 2, detected_at: created,
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
    created_at: created,
  };
}

function det(pts: number, loop = 0, camera = "CAM-02"): DetectionsMsg {
  return { type: "detections", camera_id: camera, loop, pts, frame_w: 100, frame_h: 100, tracks: [] };
}

const updated = (i: Incident) => ({ type: "incident.updated" as const, incident: i });

describe("cmsReducer", () => {
  it("stores incident and sets activeAlertId for PENDING_REVIEW", () => {
    const s = cmsReducer(initialCmsState, updated(incident("A", "PENDING_REVIEW")));
    expect(s.incidents["A"].status).toBe("PENDING_REVIEW");
    expect(s.activeAlertId).toBe("A");
  });

  it("does not activate candidates, AI-rejected or already decided incidents", () => {
    let s = cmsReducer(initialCmsState, updated(incident("A", "CANDIDATE")));
    s = cmsReducer(s, updated(incident("B", "AI_REJECTED")));
    s = cmsReducer(s, updated(incident("C", "ESCALATED")));
    expect(s.activeAlertId).toBeNull();
    expect(Object.keys(s.incidents)).toHaveLength(3);
  });

  it("clears activeAlertId when incident approved or rejected and advances to next pending", () => {
    let s = cmsReducer(initialCmsState, updated(incident("B", "PENDING_REVIEW", "2026-10-11T04:00:10Z")));
    s = cmsReducer(s, updated(incident("A", "PENDING_REVIEW", "2026-10-11T04:00:00Z")));
    expect(s.activeAlertId).toBe("A"); // oldest pending first
    s = cmsReducer(s, updated(incident("A", "APPROVED", "2026-10-11T04:00:00Z")));
    expect(s.activeAlertId).toBe("B");
    s = cmsReducer(s, updated(incident("B", "REJECTED", "2026-10-11T04:00:10Z")));
    expect(s.activeAlertId).toBeNull();
  });

  it("drops detections older than 5s", () => {
    let s = initialCmsState;
    for (const pts of [0, 1, 2, 3, 4, 5, 6, 7]) s = cmsReducer(s, det(pts));
    const kept = s.detections["CAM-02"].map((d) => d.pts);
    expect(kept).toEqual([2, 3, 4, 5, 6, 7]);
  });

  it("clears camera detections when loop changes", () => {
    let s = cmsReducer(initialCmsState, det(20, 0));
    s = cmsReducer(s, det(21, 0));
    s = cmsReducer(s, det(5, 0, "CAM-07"));
    s = cmsReducer(s, det(0.1, 1));
    expect(s.detections["CAM-02"].map((d) => d.pts)).toEqual([0.1]);
    expect(s.detections["CAM-07"]).toHaveLength(1); // other cameras untouched
  });

  it("stores sync per camera", () => {
    const sync = { type: "camera.sync" as const, camera_id: "CAM-02", loop: 0, pts: 3, wall_time: 1000 };
    expect(cmsReducer(initialCmsState, sync).sync["CAM-02"]).toEqual(sync);
  });

  it("incidents.loaded restores pending alert without losing newer websocket data", () => {
    let s = cmsReducer(initialCmsState, updated(incident("A", "PENDING_REVIEW")));
    s = cmsReducer(s, { type: "incidents.loaded", incidents: [incident("A", "APPROVED"), incident("B", "PENDING_REVIEW")] });
    expect(s.incidents["A"].status).toBe("APPROVED"); // server truth wins
    expect(s.activeAlertId).toBe("B");
  });

  it("removes a deleted incident and moves the alert card to the next pending one", () => {
    let s = cmsReducer(initialCmsState, updated(incident("A", "PENDING_REVIEW", "2026-10-11T04:00:00Z")));
    s = cmsReducer(s, updated(incident("B", "PENDING_REVIEW", "2026-10-11T04:00:10Z")));
    expect(s.activeAlertId).toBe("A");
    s = cmsReducer(s, { type: "incident.deleted", id: "A" });
    expect(Object.keys(s.incidents)).toEqual(["B"]);
    expect(s.activeAlertId).toBe("B");
    expect(cmsReducer(s, { type: "incident.deleted", id: "nope" }).incidents).toEqual(s.incidents); // unknown id: no-op
  });

  it("starts looping and follows playback messages", () => {
    expect(initialCmsState.playback).toEqual({ loop: true, held: false, paused: false });
    const s = cmsReducer(initialCmsState, { type: "playback", loop: false, held: true, paused: true });
    expect(s.playback).toEqual({ loop: false, held: true, paused: true });
  });

  it("batch applies actions in order", () => {
    const s = cmsReducer(initialCmsState, {
      type: "batch",
      actions: [det(1), det(2), updated(incident("A", "PENDING_REVIEW"))],
    });
    expect(s.detections["CAM-02"]).toHaveLength(2);
    expect(s.activeAlertId).toBe("A");
  });
});

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }
  close() {
    this.closed = true;
    this.onclose?.();
  }
  open() {
    this.onopen?.();
  }
  drop() {
    this.onclose?.();
  }
  push(msg: unknown) {
    this.onmessage?.({ data: JSON.stringify(msg) });
  }
}

describe("useCmsSocket", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.mocked(getIncidents).mockReset();
    vi.mocked(getPlayback).mockReset();
    vi.mocked(getPlayback).mockResolvedValue({ loop: true, held: false, paused: false });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("reload after reconnect restores pending alert", async () => {
    vi.mocked(getIncidents).mockResolvedValue([incident("A", "PENDING_REVIEW")]);
    const { result } = renderHook(() => useCmsSocket());
    expect(result.current.connected).toBe(false);

    act(() => FakeWebSocket.instances[0].open());
    await waitFor(() => expect(result.current.state.activeAlertId).toBe("A"));
    expect(result.current.connected).toBe(true);
    expect(getIncidents).toHaveBeenCalledTimes(1);

    // connection drops mid-incident; the alert card must survive and be reloaded after reconnect
    vi.useFakeTimers({ shouldAdvanceTime: true });
    act(() => FakeWebSocket.instances[0].drop());
    expect(result.current.connected).toBe(false);
    expect(result.current.state.activeAlertId).toBe("A"); // not lost while offline
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(FakeWebSocket.instances).toHaveLength(2);
    act(() => FakeWebSocket.instances[1].open());
    await waitFor(() => expect(getIncidents).toHaveBeenCalledTimes(2));
    expect(result.current.connected).toBe(true);
  });

  it("restores a pending alert after a page reload (fresh state, REST reload on connect)", async () => {
    vi.mocked(getIncidents).mockResolvedValue([incident("A", "PENDING_REVIEW")]);
    const { result } = renderHook(() => useCmsSocket());
    expect(result.current.state.activeAlertId).toBeNull();
    act(() => FakeWebSocket.instances[0].open());
    await waitFor(() => expect(result.current.state.activeAlertId).toBe("A"));
  });

  it("applies websocket messages", async () => {
    vi.mocked(getIncidents).mockResolvedValue([]);
    const { result } = renderHook(() => useCmsSocket());
    act(() => FakeWebSocket.instances[0].open());
    act(() => FakeWebSocket.instances[0].push(updated(incident("Z", "PENDING_REVIEW"))));
    await waitFor(() => expect(result.current.state.activeAlertId).toBe("Z"));
  });

  it("backs off 1s, 2s, then 5s between reconnect attempts", async () => {
    vi.mocked(getIncidents).mockResolvedValue([]);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderHook(() => useCmsSocket());
    const delays = [1000, 2000, 5000, 5000];
    for (let i = 0; i < delays.length; i++) {
      expect(FakeWebSocket.instances).toHaveLength(i + 1);
      act(() => FakeWebSocket.instances[i].drop());
      await act(async () => {
        await vi.advanceTimersByTimeAsync(delays[i] - 1);
      });
      expect(FakeWebSocket.instances).toHaveLength(i + 1); // not yet
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(FakeWebSocket.instances).toHaveLength(i + 2);
    }
  });

  it("stops reconnecting after unmount", async () => {
    vi.mocked(getIncidents).mockResolvedValue([]);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { unmount } = renderHook(() => useCmsSocket());
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("applyIncident puts a REST response into state without waiting for the socket", async () => {
    vi.mocked(getIncidents).mockResolvedValue([]);
    const { result } = renderHook(() => useCmsSocket());
    act(() => result.current.applyIncident(incident("A", "APPROVED")));
    expect(result.current.state.incidents["A"].status).toBe("APPROVED");
  });

  it("loads the playback state on connect, so a page reload shows the right button", async () => {
    vi.mocked(getIncidents).mockResolvedValue([]);
    vi.mocked(getPlayback).mockResolvedValue({ loop: false, held: true, paused: false });
    const { result } = renderHook(() => useCmsSocket());
    act(() => FakeWebSocket.instances[0].open());
    await waitFor(() => expect(result.current.state.playback).toEqual({ loop: false, held: true, paused: false }));
  });
});
