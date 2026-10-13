"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { getIncidents, getPlayback, wsUrl } from "./api";
import type { DetectionsMsg, Incident, PlaybackState, SyncMsg, WsMsg } from "./types";

export const DETECTION_WINDOW_S = 5;
const BACKOFF_MS = [1000, 2000, 5000];

export interface CmsState {
  incidents: Record<string, Incident>;
  detections: Record<string, DetectionsMsg[]>; // last 5 s per camera, ordered by pts
  sync: Record<string, SyncMsg>;
  activeAlertId: string | null; // the oldest PENDING_REVIEW incident
  playback: PlaybackState;
}

export const initialCmsState: CmsState = {
  incidents: {},
  detections: {},
  sync: {},
  activeAlertId: null,
  playback: { loop: true, held: false },
};

export type CmsAction =
  | WsMsg
  | { type: "incidents.loaded"; incidents: Incident[] }
  | { type: "batch"; actions: CmsAction[] };

function pickActive(incidents: Record<string, Incident>): string | null {
  let best: Incident | null = null;
  for (const inc of Object.values(incidents)) {
    if (inc.status !== "PENDING_REVIEW") continue;
    if (best === null || Date.parse(inc.created_at) < Date.parse(best.created_at)) best = inc;
  }
  return best ? best.id : null;
}

function withIncidents(state: CmsState, incidents: Record<string, Incident>): CmsState {
  return { ...state, incidents, activeAlertId: pickActive(incidents) };
}

function addDetections(state: CmsState, msg: DetectionsMsg): CmsState {
  const prev = state.detections[msg.camera_id] ?? [];
  const last = prev[prev.length - 1];
  // a clip wrap restarts pts and track ids: never keep boxes from the previous loop
  const base = last && last.loop !== msg.loop ? [] : prev;
  const kept = base.filter((d) => d.pts >= msg.pts - DETECTION_WINDOW_S);
  return { ...state, detections: { ...state.detections, [msg.camera_id]: [...kept, msg] } };
}

export function cmsReducer(state: CmsState, action: CmsAction): CmsState {
  switch (action.type) {
    case "incident.updated":
      return withIncidents(state, { ...state.incidents, [action.incident.id]: action.incident });
    case "incident.deleted": {
      if (!(action.id in state.incidents)) return state;
      const rest = { ...state.incidents };
      delete rest[action.id];
      return withIncidents(state, rest);
    }
    case "incidents.loaded": {
      const next = { ...state.incidents };
      for (const inc of action.incidents) next[inc.id] = inc; // server truth wins
      return withIncidents(state, next);
    }
    case "detections":
      return addDetections(state, action);
    case "playback":
      return { ...state, playback: { loop: action.loop, held: action.held } };
    case "camera.sync":
      return { ...state, sync: { ...state.sync, [action.camera_id]: action } };
    case "batch":
      return action.actions.reduce(cmsReducer, state);
    default:
      return state;
  }
}

export function backoffMs(attempt: number): number {
  return BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)];
}

/** One WebSocket to the backend. On every (re)connect the incidents are reloaded over REST,
 *  so a dropped socket or a page refresh never loses a pending alert. */
export function useCmsSocket(): {
  state: CmsState;
  connected: boolean;
  applyIncident: (incident: Incident) => void;
  removeIncident: (id: string) => void;
} {
  const [state, dispatch] = useReducer(cmsReducer, initialCmsState);
  const [connected, setConnected] = useState(false);
  const queue = useRef<CmsAction[]>([]);

  useEffect(() => {
    let disposed = false;
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let raf: number | null = null;
    let attempt = 0;

    // detections arrive at camera frame rate: apply them once per animation frame
    const flush = () => {
      raf = null;
      if (queue.current.length === 0) return;
      const actions = queue.current;
      queue.current = [];
      dispatch({ type: "batch", actions });
    };
    const enqueue = (action: CmsAction) => {
      queue.current.push(action);
      if (raf === null) {
        raf =
          typeof requestAnimationFrame === "function"
            ? requestAnimationFrame(flush)
            : (setTimeout(flush, 16) as unknown as number);
      }
    };

    const connect = () => {
      if (disposed) return;
      ws = new WebSocket(wsUrl());
      ws.onopen = () => {
        attempt = 0;
        setConnected(true);
        getIncidents()
          .then((incidents) => {
            if (!disposed) dispatch({ type: "incidents.loaded", incidents });
          })
          .catch(() => undefined); // the next reconnect reloads again
        getPlayback()
          .then((p) => {
            if (!disposed) dispatch({ type: "playback", ...p });
          })
          .catch(() => undefined);
      };
      ws.onmessage = (e) => {
        try {
          enqueue(JSON.parse(e.data) as WsMsg);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (disposed) return;
        timer = setTimeout(connect, backoffMs(attempt));
        attempt += 1;
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      if (raf !== null && typeof cancelAnimationFrame === "function") cancelAnimationFrame(raf);
      ws?.close();
    };
  }, []);

  // REST responses to guard actions go straight into state, so the card never waits on the socket
  const applyIncident = useCallback(
    (incident: Incident) => dispatch({ type: "incident.updated", incident }),
    [],
  );

  const removeIncident = useCallback((id: string) => dispatch({ type: "incident.deleted", id }), []);

  return { state, connected, applyIncident, removeIncident };
}
