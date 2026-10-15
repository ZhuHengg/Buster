"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { clipUrl } from "@/lib/api";
import { expectedPts, fitTransform, nearestDetections } from "@/lib/overlay";
import { formatAge, formatClock, STALE_AFTER_MS, STREAM_META, type StreamInfo } from "@/lib/stream";
import type { CameraConfig, DetectionsMsg, PlaybackState, SyncMsg } from "@/lib/types";

import Icon from "./Icon";

const RESYNC_THRESHOLD_S = 0.3;
const WATCHDOG_MS = 500;
const NO_DATA_AFTER_MS = 10_000;

export type FitMode = "contain" | "cover";

export interface CameraTileProps {
  camera: CameraConfig;
  detections: DetectionsMsg[];
  sync: SyncMsg | undefined;
  alerting: boolean;
  playback?: PlaybackState;
  fit?: FitMode;
  /** Enlarged single-camera view is showing this tile. */
  focused?: boolean;
  onToggleFocus?: (id: string) => void;
  /** Stream health, derived from the video element; called with null on unmount. */
  onStream?: (id: string, info: StreamInfo | null) => void;
  /** Compact tile (filmstrip): hides secondary text. */
  compact?: boolean;
}

const INITIAL: StreamInfo = { state: "CONNECTING", detail: "Opening video source…", lastFrameAt: null };

export default function CameraTile({
  camera,
  detections,
  sync,
  alerting,
  playback = { loop: true, held: false, paused: false },
  fit = "contain",
  focused = false,
  onToggleFocus,
  onStream,
  compact = false,
}: CameraTileProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const detRef = useRef(detections);
  const syncRef = useRef(sync);
  const loopRef = useRef(playback.loop);
  const pausedRef = useRef(playback.paused);
  const fitRef = useRef(fit);
  useEffect(() => {
    detRef.current = detections;
    syncRef.current = sync;
    loopRef.current = playback.loop;
    pausedRef.current = playback.paused;
    fitRef.current = fit;
  });

  const hasSource = camera.clip !== null;
  const [info, setInfo] = useState<StreamInfo>(
    hasSource ? INITIAL : { state: "OFFLINE", detail: "No video source is configured for this camera.", lastFrameAt: null },
  );
  const [now, setNow] = useState(0);
  const [position, setPosition] = useState<number | null>(null);
  const [ended, setEnded] = useState(false);
  const lastTime = useRef(-1);
  const startedAt = useRef(0);
  const failed = useRef(false);
  const resumedAt = useRef(0);

  const setState = useCallback((next: Partial<StreamInfo> & Pick<StreamInfo, "state" | "detail">) => {
    setInfo((cur) => ({ lastFrameAt: cur.lastFrameAt, ...next }));
  }, []);

  // publish to the dashboard (counts, header) only when the state actually changes
  useEffect(() => {
    onStream?.(camera.id, info);
  }, [camera.id, info, onStream]);
  useEffect(() => () => onStream?.(camera.id, null), [camera.id, onStream]);

  // a failed load: ask the server why, so "missing file", "server down" and "undecodable" read differently
  const diagnose = useCallback(async () => {
    if (!camera.clip) return;
    failed.current = true;
    try {
      const res = await fetch(clipUrl(camera.clip), { headers: { Range: "bytes=0-0" } });
      if (res.status === 404) {
        setState({ state: "NO_SIGNAL", detail: `Source file ${camera.clip} was not found on the server (HTTP 404).` });
      } else if (!res.ok) {
        setState({ state: "NO_SIGNAL", detail: `The video server answered HTTP ${res.status}.` });
      } else {
        setState({ state: "ERROR", detail: "The video was received but could not be decoded." });
      }
    } catch {
      setState({ state: "OFFLINE", detail: "The video server cannot be reached." });
    }
  }, [camera.clip, setState]);

  const retry = useCallback(() => {
    const video = videoRef.current;
    if (!video || !camera.clip) return;
    failed.current = false;
    lastTime.current = -1;
    startedAt.current = Date.now();
    setEnded(false);
    setInfo({ state: "CONNECTING", detail: "Reconnecting…", lastFrameAt: null });
    video.load();
    void video.play().catch(() => undefined);
  }, [camera.clip]);

  // Stream-health watchdog. A frame only counts when the playhead really advanced.
  useEffect(() => {
    if (!hasSource) return;
    startedAt.current = Date.now();
    const id = setInterval(() => {
      const video = videoRef.current;
      if (!video) return;
      const t = Date.now();
      setNow(t);
      setPosition(video.currentTime);
      if (failed.current) return;
      if (pausedRef.current || video.ended) return; // deliberate hold: not a fault
      const advanced = Math.abs(video.currentTime - lastTime.current) > 0.01;
      lastTime.current = video.currentTime;
      if (advanced && video.readyState >= 2) {
        setInfo((cur) =>
          cur.state === "LIVE"
            ? { ...cur, lastFrameAt: t }
            : { state: "LIVE", detail: "Receiving frames.", lastFrameAt: t },
        );
        return;
      }
      setInfo((cur) => {
        if (cur.lastFrameAt === null) {
          return t - startedAt.current > NO_DATA_AFTER_MS && cur.state === "CONNECTING"
            ? { ...cur, state: "NO_SIGNAL", detail: "No data received from the source after 10 seconds." }
            : cur;
        }
        if (t - Math.max(cur.lastFrameAt, resumedAt.current) > STALE_AFTER_MS && cur.state !== "STALE") {
          return { ...cur, state: "STALE", detail: "The picture has stopped updating." };
        }
        return cur;
      });
    }, WATCHDOG_MS);
    return () => clearInterval(id);
  }, [hasSource]);

  // freeze on the current frame while paused; on resume the sync loop below re-aligns the clip
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (playback.paused) video.pause();
    else {
      // after a hold the playhead is expected to restart: don't count the hold as a stale period
      resumedAt.current = Date.now();
      void video.play().catch(() => undefined);
    }
  }, [playback.paused]);

  const duration = camera.sync?.duration;

  useEffect(() => {
    if (!camera.clip) return;
    let raf = 0;
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas) return;

      // keep the video on the pipeline's clock; the wrap-around distance counts as small drift
      const s = syncRef.current;
      if (s && duration && !pausedRef.current && !video.seeking && video.readyState >= 2) {
        const looping = loopRef.current;
        const target = expectedPts(s, Date.now() / 1000, duration, looping);
        const drift = Math.abs(video.currentTime - target);
        // looping: the wrap-around distance counts as small drift; playing once there is no wrap
        if ((looping ? Math.min(drift, duration - drift) : drift) > RESYNC_THRESHOLD_S) {
          video.currentTime = target;
          // a restart arrives as a new pass while the video sits ended or paused on its last frame
          if (video.paused && target < duration - RESYNC_THRESHOLD_S) void video.play().catch(() => undefined);
        }
      }

      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const det = nearestDetections(detRef.current, video.currentTime);
      if (!det) return; // nothing close in time (e.g. just after the clip looped): draw no stale boxes
      const { scale, offsetX, offsetY } = fitTransform(det.frame_w, det.frame_h, w, h, fitRef.current);
      ctx.lineWidth = 2;
      ctx.font = "12px ui-monospace, Consolas, monospace";
      for (const t of det.tracks) {
        const [x1, y1, x2, y2] = t.bbox;
        const x = offsetX + x1 * scale;
        const y = offsetY + y1 * scale;
        const bw = (x2 - x1) * scale;
        const bh = (y2 - y1) * scale;
        const colour = t.suspect ? "#ff4d4f" : "#ffffff";
        ctx.strokeStyle = colour;
        ctx.strokeRect(x, y, bw, bh);
        const label = t.suspect ? `SUSPECT #${t.id}` : `#${t.id}`;
        const tw = ctx.measureText(label).width + 6;
        ctx.fillStyle = t.suspect ? "#d81921" : "rgba(0,0,0,0.65)";
        ctx.fillRect(x, Math.max(0, y - 16), tw, 16);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(label, x + 3, Math.max(12, y - 4));
      }
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [camera.clip, duration]);

  const meta = STREAM_META[info.state];
  const showVideo = hasSource && (info.state === "LIVE" || info.state === "STALE" || (info.state === "CONNECTING" && info.lastFrameAt !== null));
  const blocked = info.state === "NO_SIGNAL" || info.state === "OFFLINE" || info.state === "ERROR";
  const frameAge = info.lastFrameAt !== null && now ? now - info.lastFrameAt : null;
  const w = camera.sync?.width;
  const h = camera.sync?.height;
  const portrait = !!w && !!h && h > w;

  let frameText: string;
  if (info.state === "LIVE" && position !== null) frameText = formatClock(position);
  else if (info.lastFrameAt !== null && frameAge !== null) frameText = `last frame ${formatAge(frameAge)} ago`;
  else frameText = "no frame received";

  return (
    <section
      aria-label={`${camera.id} ${camera.name}: ${meta.label}`}
      data-testid={`tile-${camera.id}`}
      data-stream-state={info.state}
      className={`@container relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[var(--r-lg)] border bg-panel ${
        alerting ? "border-[3px] border-brand" : focused ? "border-[2px] border-info" : "border-line"
      }`}
    >
      <header className="flex h-8 shrink-0 items-center gap-2 px-2 text-xs text-white">
        <span
          className={`flex shrink-0 items-center gap-1 rounded-[var(--r-sm)] px-1.5 py-0.5 text-[11px] font-bold tracking-wide ${meta.chip}`}
        >
          <Icon name={meta.icon} size={12} className={info.state === "CONNECTING" ? "spin" : ""} />
          {meta.label}
        </span>
        <span className="mono-time shrink-0 font-semibold">{camera.id}</span>
        <span className="hidden min-w-0 flex-1 truncate text-[#c9ced6] @[22rem]:block">
          {camera.name}
          {!compact && <span className="hidden @[34rem]:inline"> · {camera.location}</span>}
        </span>
        <span className="flex-1 @[22rem]:hidden" />
        {alerting && (
          <span className="shrink-0 rounded-[var(--r-sm)] bg-brand px-1.5 py-0.5 text-[11px] font-bold">INCIDENT</span>
        )}
        {camera.analyse && !compact && (
          <span
            className="hidden shrink-0 items-center gap-1 text-[#c9ced6] @[24rem]:flex"
            title="This camera is analysed by the AI detector"
          >
            <Icon name="cpu" size={12} />
            AI
          </span>
        )}
        {!blocked && (
          <span className="mono-time hidden shrink-0 text-[#c9ced6] @[12rem]:inline" title="Position of the displayed frame in the recorded clip">
            {frameText}
          </span>
        )}
        {meta.fault && hasSource && (
          <button
            type="button"
            onClick={retry}
            aria-label={`Retry connection to ${camera.id}`}
            title="Retry connection"
            className="on-dark flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--r-sm)] hover:bg-white/15"
          >
            <Icon name="retry" size={14} />
          </button>
        )}
        {onToggleFocus && (
          <button
            type="button"
            onClick={() => onToggleFocus(camera.id)}
            aria-label={focused ? `Return to grid from ${camera.id}` : `Enlarge ${camera.id}`}
            aria-pressed={focused}
            title={focused ? "Back to grid" : "Enlarge this camera"}
            className="on-dark flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--r-sm)] hover:bg-white/15"
          >
            <Icon name={focused ? "collapse" : "expand"} size={14} />
          </button>
        )}
      </header>

      <div
        className="relative min-h-0 flex-1 bg-video"
        onDoubleClick={() => onToggleFocus?.(camera.id)}
      >
        {hasSource && (
          <>
            <video
              ref={videoRef}
              src={clipUrl(camera.clip!)}
              className={`absolute inset-0 h-full w-full ${fit === "cover" ? "object-cover" : "object-contain"} ${
                showVideo ? "" : "invisible"
              } ${info.state === "STALE" ? "opacity-60" : ""}`}
              muted
              loop={playback.loop}
              playsInline
              autoPlay
              preload="auto"
              aria-hidden="true"
              onLoadedMetadata={(e) => void e.currentTarget.play().catch(() => undefined)}
              onError={() => void diagnose()}
              onEnded={() => setEnded(true)}
              onPlaying={() => setEnded(false)}
            />
            <canvas
              ref={canvasRef}
              className={`pointer-events-none absolute inset-0 h-full w-full ${showVideo ? "" : "invisible"}`}
            />
          </>
        )}

        {info.state === "CONNECTING" && !showVideo && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-[#bfdbfe]">
            <Icon name="spinner" size={28} className="spin" />
            <span className="text-sm font-semibold">Connecting to {camera.id}…</span>
            <span className="px-4 text-center text-xs text-[#9aa4b2]">{info.detail}</span>
          </div>
        )}

        {blocked && (
          <div
            role="status"
            className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 overflow-hidden bg-video px-4 text-center"
          >
            <span className={`flex items-center justify-center rounded-full ${meta.chip} ${compact ? "h-7 w-7" : "h-11 w-11"}`}>
              <Icon name={meta.icon} size={compact ? 16 : 24} />
            </span>
            {!compact && <span className="text-sm font-bold tracking-wide text-white">{meta.label}</span>}
            {!compact && (
              <>
                <span className="line-clamp-2 max-w-[22rem] text-xs leading-snug text-[#9aa4b2]">{info.detail}</span>
                {info.lastFrameAt !== null && frameAge !== null && (
                  <span className="mono-time text-[11px] text-[#9aa4b2]">Last frame {formatAge(frameAge)} ago</span>
                )}
              </>
            )}
            {hasSource && !compact && (
              <button
                type="button"
                onClick={retry}
                className="on-dark mt-1.5 flex items-center gap-1.5 rounded-full bg-brand px-4 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-brand-strong"
              >
                <Icon name="retry" size={14} />
                Retry connection
              </button>
            )}
          </div>
        )}

        {info.state === "STALE" && (
          <div
            role="status"
            className="absolute inset-x-0 bottom-0 flex items-center gap-2 bg-[#78350f] px-3 py-1.5 text-xs font-semibold text-[#fde68a]"
          >
            <Icon name="stale" size={14} />
            <span className="flex-1 truncate">
              STALE: no new frame for {frameAge !== null ? formatAge(frameAge) : "—"}. Picture shown is out of date.
            </span>
            <button
              type="button"
              onClick={retry}
              className="on-dark rounded-[var(--r-sm)] bg-[#fde68a] px-2 py-0.5 text-[#78350f] hover:bg-white"
            >
              Retry
            </button>
          </div>
        )}

        {showVideo && playback.paused && (
          <div className="pointer-events-none absolute left-1/2 top-2 -translate-x-1/2">
            <span className="flex items-center gap-1.5 rounded-[var(--r-sm)] bg-black/75 px-2 py-1 text-xs font-semibold text-[#fde68a]">
              <Icon name="pause" size={12} />
              Paused
            </span>
          </div>
        )}
        {showVideo && !playback.paused && ended && !playback.loop && (
          <div className="pointer-events-none absolute left-1/2 top-2 -translate-x-1/2">
            <span className="rounded-[var(--r-sm)] bg-black/75 px-2 py-1 text-xs font-semibold text-white">
              Clip finished, holding last frame
            </span>
          </div>
        )}

        {showVideo && w && h && !compact && (
          <span className="mono-time pointer-events-none absolute bottom-1 left-1.5 rounded-[var(--r-sm)] bg-black/60 px-1.5 py-0.5 text-[11px] text-[#d1d5db]">
            {w}×{h}
            {portrait ? " portrait" : ""}
            {fit === "cover" ? " · cropped to fill" : ""}
          </span>
        )}
      </div>
    </section>
  );
}
