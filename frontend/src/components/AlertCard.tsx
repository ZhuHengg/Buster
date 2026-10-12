"use client";

import { useEffect, useRef, useState } from "react";

import { clipUrl, snapshotUrl } from "@/lib/api";
import type { CameraConfig, Incident } from "@/lib/types";

import EscalationTimeline from "./EscalationTimeline";

export interface AlertCardProps {
  incident: Incident;
  camera: CameraConfig | undefined;
  onApprove: () => void;
  onReject: () => void;
  onClose: () => void; // only offered once the alert has been decided
  busy: boolean;
  queueCount?: number; // other alerts still waiting behind this one
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function useElapsedSeconds(iso: string): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return Math.max(0, Math.floor((now - Date.parse(iso)) / 1000));
}

function formatElapsed(total: number): string {
  if (total >= 3600) return `${Math.floor(total / 3600)}h ${Math.floor((total % 3600) / 60)}m`;
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function Kbd({ children }: { children: string }) {
  return (
    <kbd aria-hidden className="ml-2 rounded border border-white/40 px-1.5 py-0.5 font-mono text-[11px] font-normal">
      {children}
    </kbd>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[92px_1fr] gap-3 border-b border-line/70 py-1.5 text-sm last:border-b-0">
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-slate-100">{children}</dd>
    </div>
  );
}

export default function AlertCard({
  incident,
  camera,
  onApprove,
  onReject,
  onClose,
  busy,
  queueCount = 0,
}: AlertCardProps) {
  const v = incident.verification;
  const pending = incident.status === "PENDING_REVIEW";
  const acted = useRef(false);
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const elapsed = useElapsedSeconds(incident.candidate.detected_at);

  // a failed request (busy goes true -> false while still pending) lets the guard try again
  useEffect(() => {
    if (!busy) acted.current = false;
  }, [busy]);

  const act = (fn: () => void) => () => {
    if (acted.current || busy) return;
    acted.current = true;
    fn();
  };
  const keysRef = useRef({
    approve: () => undefined as void,
    reject: () => undefined as void,
  });
  useEffect(() => {
    keysRef.current = { approve: act(onApprove), reject: act(onReject) };
  });

  // the panel is not modal (the cameras stay usable), so move focus into it rather than trapping it.
  // The panel itself gets focus, never the Approve button: a stray Enter must not escalate.
  useEffect(() => {
    (pending ? panelRef.current : closeRef.current)?.focus({
      preventScroll: true,
    });
  }, [incident.id, pending]);

  useEffect(() => {
    if (pending) {
      const onKey = (e: KeyboardEvent) => {
        if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
        const t = e.target as HTMLElement | null;
        if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
        const k = e.key.toLowerCase();
        if (k === "a") keysRef.current.approve();
        else if (k === "r") keysRef.current.reject();
      };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pending, onClose]);

  // one tone when a new alert becomes active
  useEffect(() => {
    if (incident.status !== "PENDING_REVIEW") return;
    try {
      void new Audio("/sounds/alert.mp3").play().catch(() => undefined);
    } catch {
      /* audio is best effort */
    }
  }, [incident.id, incident.status]);

  const escape =
    incident.escape_direction || incident.escape_exit
      ? [incident.escape_direction && cap(incident.escape_direction), incident.escape_exit].filter(Boolean).join(" → ")
      : "Unknown";
  const suspects = v?.suspects.map((s) => s.description).join("; ");
  const vehicle = v?.vehicle
    ? `${v.vehicle.colour} ${v.vehicle.type}${v.vehicle.plate_visible && v.vehicle.plate_text ? `, plate ${v.vehicle.plate_text}` : ""}`
    : null;
  const time = new Date(incident.candidate.detected_at).toLocaleTimeString("en-GB", { hour12: false });
  const gateLabel = incident.escape_exit ?? undefined;

  return (
    <aside
      ref={panelRef}
      tabIndex={-1}
      aria-label="Security alert"
      className="card-in flex h-full w-[480px] max-w-[45vw] shrink-0 flex-col border-l-2 border-accent bg-panel shadow-2xl"
    >
      {pending && (
        <div role="alert" className="sr-only">
          New alert on {incident.camera_id}: {v ? cap(v.incident_type.replace("_", " ")) : "suspected snatch theft"}.
          Press A to approve or R to reject.
        </div>
      )}
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">
            {pending ? "Security alert" : "Escalating"}
          </div>
          <div className="text-lg font-semibold text-slate-50">
            {v ? cap(v.incident_type.replace("_", " ")) : "Suspected snatch theft"}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-muted">
            <span>
              Detected <span className="mono-time text-slate-200">{formatElapsed(elapsed)}</span> ago
            </span>
            {pending && queueCount > 0 && (
              <span className="rounded border border-warn/60 bg-warn/10 px-1.5 py-0.5 font-medium text-warn">
                +{queueCount} more waiting
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="mono-time rounded border border-line px-2 py-1 text-xs text-muted">{incident.id}</span>
          {!pending && (
            <button
              ref={closeRef}
              type="button"
              onClick={onClose}
              aria-label="Close alert"
              title="Close (Esc)"
              className="flex h-8 w-8 items-center justify-center rounded-md border border-line text-lg leading-none text-slate-300 transition hover:bg-white/10 hover:text-white"
            >
              ×
            </button>
          )}
        </div>
      </header>

      {!pending && (
        <div className="shrink-0 border-b border-line px-5 py-3">
          <div className="mb-2 text-xs uppercase tracking-wide text-muted">
            Approved by {incident.operator ?? "operator"}
          </div>
          <EscalationTimeline compact steps={incident.escalation} gateLabel={gateLabel} />
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-5 py-4">
        {!v && (
          <div className="rounded-md border border-warn/60 bg-warn/10 px-3 py-2 text-sm font-medium text-warn">
            AI verification unavailable: operator to confirm
          </div>
        )}

        <video
          key={incident.id}
          src={clipUrl(incident.clip_file, incident.clip_start, incident.clip_end)}
          className="aspect-video w-full rounded-md border border-line bg-black object-contain"
          muted
          autoPlay
          playsInline
          controls
          onTimeUpdate={(e) => {
            const el = e.currentTarget;
            if (el.currentTime >= incident.clip_end - 0.05) {
              el.currentTime = incident.clip_start;
              void el.play().catch(() => undefined);
            }
          }}
        />

        {incident.snapshot_files.length > 0 && (
          <div>
            <div className="mb-1.5 text-xs uppercase tracking-wide text-muted">Suspect snapshots</div>
            <div className="flex gap-2">
              {incident.snapshot_files.map((file, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={file}
                  src={snapshotUrl(file)}
                  alt={`Suspect snapshot ${i + 1}`}
                  className="h-24 rounded-md border border-line bg-black object-contain"
                />
              ))}
            </div>
          </div>
        )}

        <p className="text-sm leading-relaxed text-slate-100">
          {v ? v.summary : "A motorcycle snatch theft was flagged by the detector. Review the clip and confirm."}
        </p>

        <dl className="rounded-md border border-line bg-panel2 px-3 py-1">
          <Row label="Camera">
            {incident.camera_id}
            {camera ? ` · ${camera.name}` : ""}
          </Row>
          <Row label="Location">{camera?.location ?? "—"}</Row>
          <Row label="Time">
            <span className="mono-time">{time}</span>
          </Row>
          <Row label="Confidence">{v ? <span className="mono-time">{Math.round(v.confidence * 100)}%</span> : "—"}</Row>
          {suspects && <Row label="Suspects">{suspects}</Row>}
          {vehicle && <Row label="Vehicle">{vehicle}</Row>}
          {v?.victim && <Row label="Victim">{v.victim.description}</Row>}
          <Row label="Escape">{escape}</Row>
        </dl>
      </div>

      {pending && (
        <footer className="shrink-0 border-t border-line bg-panel px-5 py-3 shadow-[0_-8px_16px_rgba(0,0,0,0.35)]">
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={act(onApprove)}
              disabled={busy}
              aria-keyshortcuts="A"
              className="rounded-md bg-accent px-4 py-3 text-sm font-semibold uppercase tracking-wide text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Approve &amp; escalate
              <Kbd>A</Kbd>
            </button>
            <button
              type="button"
              onClick={act(onReject)}
              disabled={busy}
              aria-keyshortcuts="R"
              className="rounded-md border border-slate-500 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Reject (false positive)
              <Kbd>R</Kbd>
            </button>
          </div>
        </footer>
      )}
    </aside>
  );
}
