import type { IconName } from "@/components/Icon";

/** What the operator can rely on for one camera tile. Derived from the real <video> element. */
export type StreamState = "LIVE" | "CONNECTING" | "NO_SIGNAL" | "STALE" | "OFFLINE" | "ERROR";

export interface StreamInfo {
  state: StreamState;
  /** Plain-language reason, shown on the tile. */
  detail: string;
  /** Epoch ms of the last frame that actually advanced; null if none was ever received. */
  lastFrameAt: number | null;
}

export interface StreamMeta {
  label: string;
  icon: IconName;
  /** Chip colours on the dark title bar. */
  chip: string;
  /** Chip colours on a light surface. */
  chipLight: string;
  fault: boolean;
}

export const STREAM_META: Record<StreamState, StreamMeta> = {
  LIVE: { label: "LIVE", icon: "check", chip: "bg-[#14532d] text-[#bbf7d0]", chipLight: "bg-ok-tint text-ok", fault: false },
  CONNECTING: {
    label: "CONNECTING",
    icon: "spinner",
    chip: "bg-[#1e3a5f] text-[#bfdbfe]",
    chipLight: "bg-info-tint text-info",
    fault: false,
  },
  STALE: { label: "STALE", icon: "stale", chip: "bg-[#78350f] text-[#fde68a]", chipLight: "bg-warn-tint text-warn", fault: true },
  NO_SIGNAL: {
    label: "NO SIGNAL",
    icon: "nosignal",
    chip: "bg-[#7c2d12] text-[#fed7aa]",
    chipLight: "bg-warn-tint text-warn",
    fault: true,
  },
  OFFLINE: {
    label: "OFFLINE",
    icon: "offline",
    chip: "bg-[#374151] text-[#e5e7eb]",
    chipLight: "bg-neutral-tint text-neutral",
    fault: true,
  },
  ERROR: { label: "ERROR", icon: "alert", chip: "bg-[#7f1d1d] text-[#fecaca]", chipLight: "bg-crit-tint text-crit", fault: true },
};

/** A frame older than this while the stream claims to play is STALE. */
export const STALE_AFTER_MS = 4000;

export function formatClock(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return "--:--";
  const m = Math.floor(sec / 60);
  return `${String(m).padStart(2, "0")}:${(sec % 60).toFixed(1).padStart(4, "0")}`;
}

export function formatAge(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}
