"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { getCameras } from "./api";
import type { StreamInfo } from "./stream";
import type { CameraConfig, Incident } from "./types";
import { useCmsSocket, type CmsState } from "./ws";

interface CmsContextValue {
  state: CmsState;
  connected: boolean;
  /** null until the first successful load */
  cameras: CameraConfig[] | null;
  cameraLoadFailures: number;
  applyIncident: (incident: Incident) => void;
  removeIncident: (id: string) => void;
  /** Stream health reported by the camera tiles that are mounted; absent = not measured. */
  streams: Record<string, StreamInfo>;
  reportStream: (id: string, info: StreamInfo | null) => void;
  /** Epoch ms of the last message or successful load from the backend. */
  lastSyncAt: number | null;
}

const CmsContext = createContext<CmsContextValue | null>(null);

export function CmsProvider({ children }: { children: React.ReactNode }) {
  const { state, connected, applyIncident, removeIncident } = useCmsSocket();
  const [cameras, setCameras] = useState<CameraConfig[] | null>(null);
  const [cameraLoadFailures, setFailures] = useState(0);
  const [streams, setStreams] = useState<Record<string, StreamInfo>>({});
  const [loadedAt, setLoadedAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const load = () =>
      getCameras()
        .then((list) => {
          if (cancelled) return;
          setCameras(list);
          setLoadedAt(Date.now());
        })
        .catch(() => {
          if (cancelled) return;
          setFailures((n) => n + 1);
          timer = setTimeout(load, 2000); // backend may still be starting
        });
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  // any camera.sync / detections message proves the backend pipeline is alive
  const syncStamp = useMemo(
    () => Object.values(state.sync).reduce((m, s) => Math.max(m, s.wall_time), 0),
    [state.sync],
  );
  const lastSyncAt = Math.max(loadedAt ?? 0, syncStamp * 1000) || null;

  const reportStream = useCallback((id: string, info: StreamInfo | null) => {
    setStreams((prev) => {
      if (info === null) {
        if (!(id in prev)) return prev;
        const rest = { ...prev };
        delete rest[id];
        return rest;
      }
      const cur = prev[id];
      if (cur && cur.state === info.state && cur.detail === info.detail) return prev;
      return { ...prev, [id]: info };
    });
  }, []);

  const value = useMemo<CmsContextValue>(
    () => ({
      state,
      connected,
      cameras,
      cameraLoadFailures,
      applyIncident,
      removeIncident,
      streams,
      reportStream,
      lastSyncAt,
    }),
    [state, connected, cameras, cameraLoadFailures, applyIncident, removeIncident, streams, reportStream, lastSyncAt],
  );
  return <CmsContext.Provider value={value}>{children}</CmsContext.Provider>;
}

export function useCms(): CmsContextValue {
  const ctx = useContext(CmsContext);
  if (!ctx) throw new Error("useCms must be used inside <CmsProvider>");
  return ctx;
}
