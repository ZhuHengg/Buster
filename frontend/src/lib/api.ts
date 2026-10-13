import type { CameraConfig, Incident, IncidentStatus, PlaybackState, ReportsResponse } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function wsUrl(): string {
  return API_BASE.replace(/^http/, "ws") + "/ws";
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(res.status, String(detail));
  }
  return (await res.json()) as T;
}

export const getPlayback = () => request<PlaybackState>("/api/playback");

export const setLoop = (loop: boolean) =>
  request<PlaybackState>("/api/playback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ loop }),
  });

export const restartPlayback = () => request<PlaybackState>("/api/playback/restart", { method: "POST" });

export const getReports = () => request<ReportsResponse>("/api/reports");

export const getCameras = () => request<CameraConfig[]>("/api/cameras");

export const getIncidents = (status?: IncidentStatus) =>
  request<Incident[]>("/api/incidents" + (status ? `?status=${status}` : ""));

export const getIncident = (id: string) => request<Incident>(`/api/incidents/${encodeURIComponent(id)}`);

const decide = (id: string, action: "approve" | "reject", operator: string) =>
  request<Incident>(`/api/incidents/${encodeURIComponent(id)}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator }),
  });

export const approve = (id: string, operator: string) => decide(id, "approve", operator);
export const reject = (id: string, operator: string) => decide(id, "reject", operator);

/** Original clip URL; the media fragment limits playback to [start, end]. */
export function clipUrl(file: string, start?: number, end?: number): string {
  const base = `${API_BASE}/media/clips/${encodeURIComponent(file)}`;
  if (start === undefined) return base;
  return end === undefined ? `${base}#t=${start}` : `${base}#t=${start},${end}`;
}

export const snapshotUrl = (file: string) => `${API_BASE}/media/snapshots/${encodeURIComponent(file)}`;
