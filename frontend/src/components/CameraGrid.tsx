"use client";

import { OPERATOR_NAME, TOWNSHIP_NAME } from "@/lib/config";
import type { CmsState } from "@/lib/ws";
import type { CameraConfig } from "@/lib/types";

import CameraTile from "./CameraTile";
import PlaybackControls from "./PlaybackControls";

export function CmsHeader({
  connected,
  title,
  subtitle,
  children,
}: {
  connected?: boolean; // omitted on pages that have no live connection
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-line px-5 py-3">
      <div className="min-w-0">
        <h1 className="truncate text-lg font-semibold text-slate-50">{title}</h1>
        <div className="truncate text-xs text-muted">{subtitle ?? `${TOWNSHIP_NAME} · Central Monitoring System`}</div>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
        {children}
        {connected !== undefined && (
          <span
            role="status"
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-medium ${
              connected ? "border-ok/40 bg-ok/10 text-ok" : "border-accent/50 bg-accent/10 text-red-300"
            }`}
          >
            <span className={`inline-block h-2 w-2 rounded-full ${connected ? "bg-ok" : "rec-dot bg-accent"}`} />
            {connected ? "Live" : "Reconnecting"}
          </span>
        )}
        <span className="flex items-center gap-2 rounded-full border border-line bg-panel py-1 pl-1 pr-3 text-slate-200">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-info/20 text-[11px] font-semibold text-info">
            {OPERATOR_NAME.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
          </span>
          {OPERATOR_NAME}
        </span>
      </div>
    </header>
  );
}

type StatTone = "blue" | "rose" | "mint" | "sand";

const STAT_ICONS: Record<StatTone, React.ReactNode> = {
  blue: (
    <>
      <path d="M23 7l-7 5 7 5V7z" />
      <rect x="1" y="5" width="15" height="14" rx="2" />
    </>
  ),
  rose: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </>
  ),
  mint: (
    <>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  sand: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M15 9l-6 6M9 9l6 6" />
    </>
  ),
};

function StatTile({
  tone,
  value,
  label,
  hint,
  onClick,
}: {
  tone: StatTone;
  value: string;
  label: string;
  hint: string;
  onClick?: () => void;
}) {
  const body = (
    <>
      <span className="stat-chip" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {STAT_ICONS[tone]}
        </svg>
      </span>
      <div className="relative min-w-0 flex-1">
        <div className="truncate text-sm font-semibold leading-tight">{label}</div>
        <div className="mt-0.5 flex items-center gap-1 truncate text-[11px] leading-tight opacity-70">
          {hint}
          {onClick && <span aria-hidden="true">→</span>}
        </div>
      </div>
      <div className="stat-value relative text-3xl font-bold leading-none">{value}</div>
      {onClick && <span className="stat-ping" aria-hidden="true" />}
    </>
  );
  const cls = `stat-card stat-${tone}`;
  return onClick ? (
    <button type="button" onClick={onClick} className={`${cls} stat-action`}>
      {body}
    </button>
  ) : (
    <div className={cls}>{body}</div>
  );
}

export interface CameraGridProps {
  cameras: CameraConfig[];
  state: CmsState;
  connected: boolean;
  pendingCount?: number;
  onReview?: () => void; // reopen the alert panel after it was closed
}

export default function CameraGrid({ cameras, state, connected, pendingCount = 0, onReview }: CameraGridProps) {
  const alertCamera = state.activeAlertId ? state.incidents[state.activeAlertId]?.camera_id : undefined;
  const incidents = Object.values(state.incidents);
  const online = cameras.filter((c) => c.clip !== null).length;
  const escalated = incidents.filter((i) => i.status === "ESCALATED" || i.status === "APPROVED").length;
  const dismissed = incidents.filter((i) => i.status === "REJECTED" || i.status === "AI_REJECTED").length;
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <CmsHeader
        connected={connected}
        title="Live monitoring"
        subtitle={`${online} of ${cameras.length} cameras online · ${TOWNSHIP_NAME}`}
      >
        <PlaybackControls playback={state.playback} />
        {pendingCount > 0 && onReview && (
          <button
            type="button"
            onClick={onReview}
            className="rounded-full border border-accent/60 bg-accent/15 px-3 py-1 font-semibold text-red-200 transition hover:bg-accent/25"
          >
            Review {pendingCount} {pendingCount === 1 ? "alert" : "alerts"}
          </button>
        )}
      </CmsHeader>
      <div className="grid shrink-0 grid-cols-2 gap-3 px-4 pt-4 lg:grid-cols-4">
        <StatTile tone="blue" value={`${online}/${cameras.length}`} label="Cameras online" hint="Feeds streaming now" />
        <StatTile
          tone="rose"
          value={String(pendingCount)}
          label="Awaiting your review"
          hint={pendingCount > 0 ? "Click to open" : "Nothing waiting"}
          onClick={pendingCount > 0 ? onReview : undefined}
        />
        <StatTile tone="mint" value={String(escalated)} label="Escalated to police" hint="Approved by an operator" />
        <StatTile tone="sand" value={String(dismissed)} label="Dismissed" hint="False alarms rejected" />
      </div>
      <main
        className="grid min-h-0 flex-1 grid-cols-3 gap-3 p-4"
        style={{ gridTemplateRows: `repeat(${Math.ceil(cameras.length / 3)}, minmax(0, 1fr))` }}
      >
        {cameras.map((camera) => (
          <CameraTile
            key={camera.id}
            camera={camera}
            detections={state.detections[camera.id] ?? []}
            sync={state.sync[camera.id]}
            alerting={camera.id === alertCamera}
            playback={state.playback}
          />
        ))}
      </main>
    </div>
  );
}
