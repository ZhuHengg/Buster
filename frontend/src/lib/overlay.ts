import type { DetectionsMsg, SyncMsg } from "./types";

export interface FitTransform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

/** Where a frame of frameW x frameH lands inside a boxW x boxH element with `object-fit: contain`. */
export function fitTransform(
  frameW: number,
  frameH: number,
  boxW: number,
  boxH: number,
  mode: "contain" | "cover" = "contain",
): FitTransform {
  if (frameW <= 0 || frameH <= 0 || boxW <= 0 || boxH <= 0) return { scale: 0, offsetX: 0, offsetY: 0 };
  const scale = mode === "cover" ? Math.max(boxW / frameW, boxH / frameH) : Math.min(boxW / frameW, boxH / frameH);
  return { scale, offsetX: (boxW - frameW * scale) / 2, offsetY: (boxH - frameH * scale) / 2 };
}

/** The detections whose pts is closest to the video's current time, or null if none is close enough. */
export function nearestDetections(list: DetectionsMsg[], pts: number, maxGap = 0.25): DetectionsMsg | null {
  let best: DetectionsMsg | null = null;
  let bestGap = Infinity;
  for (const d of list) {
    const gap = Math.abs(d.pts - pts);
    if (gap < bestGap) {
      best = d;
      bestGap = gap;
    }
  }
  return best !== null && bestGap <= maxGap ? best : null;
}

/** Where the clip should be now, extrapolating the last sync message (now = unix seconds). */
export function expectedPts(sync: SyncMsg, now: number, duration: number, wrap = true): number {
  const t = sync.pts + (now - sync.wall_time);
  // not looping: a clip that has finished holds on its last frame instead of wrapping to the start
  if (!wrap) return Math.min(Math.max(t, 0), duration);
  return ((t % duration) + duration) % duration;
}
