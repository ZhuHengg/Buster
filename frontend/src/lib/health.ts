import { STREAM_META, type StreamInfo, type StreamState } from "./stream";
import type { CameraConfig } from "./types";

export interface StreamSummary {
  total: number;
  measured: number; // cameras whose tile has reported a state
  counts: Record<StreamState, number>;
  faults: { id: string; state: StreamState }[];
}

export function summarizeStreams(cameras: CameraConfig[], streams: Record<string, StreamInfo>): StreamSummary {
  const counts: Record<StreamState, number> = { LIVE: 0, CONNECTING: 0, NO_SIGNAL: 0, STALE: 0, OFFLINE: 0, ERROR: 0 };
  const faults: StreamSummary["faults"] = [];
  let measured = 0;
  for (const cam of cameras) {
    const info = streams[cam.id];
    if (!info) continue;
    measured += 1;
    counts[info.state] += 1;
    if (STREAM_META[info.state].fault) faults.push({ id: cam.id, state: info.state });
  }
  return { total: cameras.length, measured, counts, faults };
}
