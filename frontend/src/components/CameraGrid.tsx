"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { bestGrid } from "@/lib/layout";
import type { StreamInfo } from "@/lib/stream";
import type { CameraConfig } from "@/lib/types";
import type { CmsState } from "@/lib/ws";

import CameraTile, { type FitMode } from "./CameraTile";
import Icon from "./Icon";
import PlaybackControls from "./PlaybackControls";

type Layout = "focus" | "auto" | "2x2" | "3x2" | "3x3";
const FIXED: Record<Exclude<Layout, "auto" | "focus">, { cols: number; rows: number }> = {
  "2x2": { cols: 2, rows: 2 },
  "3x2": { cols: 3, rows: 2 },
  "3x3": { cols: 3, rows: 3 },
};
const GAP = 8;

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { key: T; text: string; title: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex overflow-hidden rounded-[var(--r-md)] border border-line-strong bg-panel">
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          aria-pressed={value === o.key}
          title={o.title}
          onClick={() => onChange(o.key)}
          className={`px-2.5 py-1.5 text-xs font-semibold transition-colors ${
            value === o.key ? "bg-brand text-white" : "text-ink hover:bg-panel2"
          }`}
        >
          {o.text}
        </button>
      ))}
    </div>
  );
}

export interface CameraGridProps {
  cameras: CameraConfig[];
  state: CmsState;
  streams: Record<string, StreamInfo>;
  /** camera of the alert being reviewed; defaults to the oldest pending alert's camera */
  alertCameraId?: string;
  onStream: (id: string, info: StreamInfo | null) => void;
}

/** The monitoring workspace: layout controls plus the grid (or one enlarged camera with a filmstrip). */
export default function CameraGrid({ cameras, state, streams, alertCameraId, onStream }: CameraGridProps) {
  const alertCamera = alertCameraId ?? (state.activeAlertId ? state.incidents[state.activeAlertId]?.camera_id : undefined);
  const [layout, setLayout] = useState<Layout>("focus");
  const [fit, setFit] = useState<FitMode>("contain");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [box, setBox] = useState({ w: 0, h: 0 });
  const wellRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = wellRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setBox({ w: entry.contentRect.width, h: entry.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // the default "Focus" layout enlarges the alerting camera, else the first live one, else the first camera
  const defaultFocus =
    layout === "focus"
      ? (cameras.find((c) => c.id === alertCamera)?.id ??
        cameras.find((c) => streams[c.id]?.state === "LIVE")?.id ??
        cameras[0]?.id ??
        null)
      : null;
  const chosen = focusId && cameras.some((c) => c.id === focusId) ? focusId : null;
  const focus = chosen ?? defaultFocus;
  const toggleFocus = (id: string) => {
    if (id === focus) {
      setFocusId(null);
      setLayout("auto");
    } else setFocusId(id);
  };

  // typical footage shape drives the automatic layout: portrait feeds get more, narrower columns
  const aspect = useMemo(() => {
    const a = cameras.flatMap((c) => (c.sync && c.sync.height > 0 ? [c.sync.width / c.sync.height] : []));
    return a.length ? a.reduce((s, x) => s + x, 0) / a.length : 16 / 9;
  }, [cameras]);

  const grid = layout === "auto" || layout === "focus" ? bestGrid(cameras.length, box.w, box.h, aspect, GAP) : FIXED[layout];
  const pageSize = grid.cols * grid.rows;
  const pages = Math.max(1, Math.ceil(cameras.length / pageSize));
  const cur = Math.min(page, pages - 1);

  const others = focus ? cameras.filter((c) => c.id !== focus).length : 0;
  const containerStyle: React.CSSProperties = focus
    ? {
        gridTemplateColumns: "minmax(0, 1fr) minmax(220px, 27%)",
        gridTemplateRows: `repeat(${Math.max(others, 1)}, minmax(96px, 1fr))`,
      }
    : {
        gridTemplateColumns: `repeat(${grid.cols}, minmax(0, 1fr))`,
        gridTemplateRows: `repeat(${grid.rows}, minmax(0, 1fr))`,
      };

  let slot = 0; // position among the tiles that are not the focused one
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2">
        <div className="flex items-center gap-2">
          <Segmented
            label="Grid layout"
            value={layout}
            onChange={(v) => {
              setLayout(v);
              setFocusId(null);
              setPage(0);
            }}
            options={[
              { key: "focus", text: "Focus", title: "One large camera with the others in a column" },
              { key: "auto", text: "Auto", title: "Choose the layout that gives the footage the most space" },
              { key: "2x2", text: "2 × 2", title: "Four cameras per page" },
              { key: "3x2", text: "3 × 2", title: "Six cameras per page" },
              { key: "3x3", text: "3 × 3", title: "Nine cameras per page" },
            ]}
          />
          <Segmented
            label="Picture fit"
            value={fit}
            onChange={setFit}
            options={[
              { key: "contain", text: "Fit", title: "Show the whole picture; unused space stays black" },
              { key: "cover", text: "Fill", title: "Fill the tile; the edges of the picture are cropped" },
            ]}
          />
          {focus && (
            <button
              type="button"
              onClick={() => {
                setFocusId(null);
                setLayout("auto");
              }}
              className="flex items-center gap-1.5 rounded-[var(--r-md)] border border-line-strong bg-panel px-2.5 py-1.5 text-xs font-semibold text-ink hover:bg-panel2"
            >
              <Icon name="grid" size={14} />
              Back to grid
            </button>
          )}
          {!focus && pages > 1 && (
            <div className="flex items-center gap-1 text-xs text-ink" role="group" aria-label="Camera pages">
              <button
                type="button"
                aria-label="Previous page of cameras"
                disabled={cur === 0}
                onClick={() => setPage(cur - 1)}
                className="flex h-7 w-7 items-center justify-center rounded-[var(--r-md)] border border-line-strong bg-panel hover:bg-panel2 disabled:opacity-40"
              >
                <Icon name="chevronLeft" size={14} />
              </button>
              <span className="mono-time min-w-12 text-center">
                {cur + 1} / {pages}
              </span>
              <button
                type="button"
                aria-label="Next page of cameras"
                disabled={cur >= pages - 1}
                onClick={() => setPage(cur + 1)}
                className="flex h-7 w-7 items-center justify-center rounded-[var(--r-md)] border border-line-strong bg-panel hover:bg-panel2 disabled:opacity-40"
              >
                <Icon name="chevronRight" size={14} />
              </button>
            </div>
          )}
        </div>
        <div className="ml-auto">
          <PlaybackControls playback={state.playback} cameraCount={cameras.length} />
        </div>
      </div>

      <div ref={wellRef} className="min-h-0 flex-1">
        <div className={`grid h-full ${focus ? "overflow-y-auto" : ""}`} style={{ ...containerStyle, gap: GAP }}>
          {cameras.map((camera, index) => {
            const isFocus = camera.id === focus;
            const style: React.CSSProperties = {};
            if (focus) {
              if (isFocus) {
                style.gridColumn = 1;
                style.gridRow = `1 / span ${Math.max(others, 1)}`;
              } else {
                style.gridColumn = 2;
                style.gridRow = ++slot;
              }
            } else if (Math.floor(index / pageSize) !== cur) {
              style.display = "none"; // off-page tiles stay mounted so their stream health keeps being measured
            }
            return (
              <div key={camera.id} style={style} className="flex min-h-0 min-w-0 flex-col">
                <CameraTile
                  camera={camera}
                  detections={state.detections[camera.id] ?? []}
                  sync={state.sync[camera.id]}
                  alerting={camera.id === alertCamera}
                  playback={state.playback}
                  fit={fit}
                  focused={isFocus}
                  compact={!!focus && !isFocus}
                  onToggleFocus={toggleFocus}
                  onStream={onStream}
                />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
