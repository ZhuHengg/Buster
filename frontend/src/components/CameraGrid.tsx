"use client";

import Link from "next/link";

import { OPERATOR_NAME, TOWNSHIP_NAME } from "@/lib/config";
import type { CmsState } from "@/lib/ws";
import type { CameraConfig } from "@/lib/types";

import CameraTile from "./CameraTile";

export function CmsHeader({ connected, children }: { connected: boolean; children?: React.ReactNode }) {
  return (
    <header className="flex items-center justify-between border-b border-line bg-panel px-4 py-2">
      <div className="flex items-baseline gap-3">
        <span className="text-sm font-semibold tracking-wide text-slate-100">{TOWNSHIP_NAME}</span>
        <span className="text-xs uppercase tracking-[0.18em] text-muted">Central Monitoring System</span>
      </div>
      <div className="flex items-center gap-5 text-xs text-muted">
        {children}
        <span>
          Operator <span className="font-medium text-slate-200">{OPERATOR_NAME}</span>
        </span>
        <span className="flex items-center gap-1.5" role="status">
          <span className={`inline-block h-2 w-2 rounded-full ${connected ? "bg-ok" : "rec-dot bg-accent"}`} />
          {connected ? "Live" : "Reconnecting"}
        </span>
      </div>
    </header>
  );
}

export interface CameraGridProps {
  cameras: CameraConfig[];
  state: CmsState;
  connected: boolean;
  pendingCount?: number;
}

export default function CameraGrid({ cameras, state, connected, pendingCount = 0 }: CameraGridProps) {
  const alertCamera = state.activeAlertId ? state.incidents[state.activeAlertId]?.camera_id : undefined;
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <CmsHeader connected={connected}>
        {pendingCount > 0 && (
          <span className="rounded border border-accent/60 bg-accent/10 px-2 py-0.5 font-medium text-red-300">
            {pendingCount} pending {pendingCount === 1 ? "alert" : "alerts"}
          </span>
        )}
        <Link href="/incidents" className="text-slate-200 underline-offset-4 hover:underline">
          Incidents
        </Link>
        <Link href="/results" className="text-slate-200 underline-offset-4 hover:underline">
          Results
        </Link>
      </CmsHeader>
      <main className="grid min-h-0 flex-1 grid-cols-3 grid-rows-3 gap-2 p-2">
        {cameras.map((camera) => (
          <CameraTile
            key={camera.id}
            camera={camera}
            detections={state.detections[camera.id] ?? []}
            sync={state.sync[camera.id]}
            alerting={camera.id === alertCamera}
          />
        ))}
      </main>
    </div>
  );
}
