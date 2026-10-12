"use client";

import { useEffect, useRef, useState } from "react";

import { clipUrl } from "@/lib/api";
import { expectedPts, fitTransform, nearestDetections } from "@/lib/overlay";
import type { CameraConfig, DetectionsMsg, SyncMsg } from "@/lib/types";

const RESYNC_THRESHOLD_S = 0.3;

export interface CameraTileProps {
  camera: CameraConfig;
  detections: DetectionsMsg[];
  sync: SyncMsg | undefined;
  alerting: boolean;
}

function useClock(): string {
  const [text, setText] = useState("");
  useEffect(() => {
    const tick = () => setText(new Date().toLocaleTimeString("en-GB", { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return text;
}

export default function CameraTile({ camera, detections, sync, alerting }: CameraTileProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const detRef = useRef(detections);
  const syncRef = useRef(sync);
  useEffect(() => {
    detRef.current = detections;
    syncRef.current = sync;
  });
  const clock = useClock();
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
      if (s && duration && !video.seeking && video.readyState >= 2) {
        const target = expectedPts(s, Date.now() / 1000, duration);
        const drift = Math.abs(video.currentTime - target);
        if (Math.min(drift, duration - drift) > RESYNC_THRESHOLD_S) video.currentTime = target;
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
      const { scale, offsetX, offsetY } = fitTransform(det.frame_w, det.frame_h, w, h);
      ctx.lineWidth = 2;
      ctx.font = "11px ui-monospace, Consolas, monospace";
      for (const t of det.tracks) {
        const [x1, y1, x2, y2] = t.bbox;
        const x = offsetX + x1 * scale;
        const y = offsetY + y1 * scale;
        const bw = (x2 - x1) * scale;
        const bh = (y2 - y1) * scale;
        const colour = t.suspect ? "#ef4444" : "#ffffff";
        ctx.strokeStyle = colour;
        ctx.strokeRect(x, y, bw, bh);
        const label = t.suspect ? `SUSPECT #${t.id}` : `#${t.id}`;
        const tw = ctx.measureText(label).width + 6;
        ctx.fillStyle = t.suspect ? "#ef4444" : "rgba(0,0,0,0.65)";
        ctx.fillRect(x, Math.max(0, y - 15), tw, 15);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(label, x + 3, Math.max(11, y - 4));
      }
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [camera.clip, duration]);

  const lost = camera.clip === null;

  return (
    <div
      className={`relative min-h-0 overflow-hidden rounded-md border border-line bg-black ${
        alerting ? "tile-alerting border-accent" : ""
      }`}
      data-testid={`tile-${camera.id}`}
    >
      {lost ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#0b0e13] text-muted">
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <path d="M2 2l20 20" />
            <path d="M7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-1" />
            <path d="M9.5 4h5L16 7h4a2 2 0 0 1 2 2v7.5" />
            <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
          </svg>
          <span className="font-mono text-xs tracking-[0.3em]">SIGNAL LOST</span>
        </div>
      ) : (
        <>
          <video
            ref={videoRef}
            src={clipUrl(camera.clip!)}
            className="absolute inset-0 h-full w-full object-contain"
            muted
            loop
            playsInline
            autoPlay
            preload="auto"
            onLoadedMetadata={(e) => void e.currentTarget.play().catch(() => undefined)}
          />
          <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 h-full w-full" />
        </>
      )}
      <div className="pointer-events-none absolute left-0 right-0 top-0 flex items-start justify-between gap-2 bg-gradient-to-b from-black/80 to-transparent px-2.5 py-1.5">
        <span className="truncate font-mono text-[11px] font-medium uppercase tracking-wide text-slate-100">
          {camera.id} · {camera.name}
        </span>
        <span className="flex shrink-0 items-center gap-1.5 font-mono text-[11px] text-slate-100">
          {!lost && <span role="img" aria-label="recording" className="inline-block h-2 w-2 rounded-full bg-accent" />}
          <span className="mono-time">{clock}</span>
        </span>
      </div>
    </div>
  );
}
