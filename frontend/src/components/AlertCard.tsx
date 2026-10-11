"use client";

import { useEffect, useRef } from "react";

import { clipUrl, snapshotUrl } from "@/lib/api";
import type { CameraConfig, Incident } from "@/lib/types";

import EscalationTimeline from "./EscalationTimeline";

export interface AlertCardProps {
  incident: Incident;
  camera: CameraConfig | undefined;
  onApprove: () => void;
  onReject: () => void;
  busy: boolean;
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[92px_1fr] gap-3 border-b border-line/70 py-1.5 text-sm last:border-b-0">
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-slate-100">{children}</dd>
    </div>
  );
}

export default function AlertCard({ incident, camera, onApprove, onReject, busy }: AlertCardProps) {
  const v = incident.verification;
  const pending = incident.status === "PENDING_REVIEW";
  const acted = useRef(false);

  // a failed request (busy goes true -> false while still pending) lets the guard try again
  useEffect(() => {
    if (!busy) acted.current = false;
  }, [busy]);

  // one tone when a new alert becomes active
  useEffect(() => {
    if (incident.status !== "PENDING_REVIEW") return;
    try {
      void new Audio("/sounds/alert.mp3").play().catch(() => undefined);
    } catch {
      /* audio is best effort */
    }
  }, [incident.id, incident.status]);

  const act = (fn: () => void) => () => {
    if (acted.current || busy) return;
    acted.current = true;
    fn();
  };

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
    <div className="fixed inset-0 z-50 flex justify-end bg-black/55" role="dialog" aria-label="Security alert">
      <section className="card-in flex h-full w-full max-w-[480px] flex-col border-l-2 border-accent bg-panel shadow-2xl">
        <header className="flex shrink-0 items-center justify-between border-b border-line px-5 py-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">
              {pending ? "Security alert" : "Escalating"}
            </div>
            <div className="text-lg font-semibold text-slate-50">
              {v ? cap(v.incident_type.replace("_", " ")) : "Suspected snatch theft"}
            </div>
          </div>
          <span className="mono-time rounded border border-line px-2 py-1 text-xs text-muted">{incident.id}</span>
        </header>

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
            <Row label="Confidence">
              {v ? <span className="mono-time">{Math.round(v.confidence * 100)}%</span> : "—"}
            </Row>
            {suspects && <Row label="Suspects">{suspects}</Row>}
            {vehicle && <Row label="Vehicle">{vehicle}</Row>}
            {v?.victim && <Row label="Victim">{v.victim.description}</Row>}
            <Row label="Escape">{escape}</Row>
          </dl>
        </div>

        <footer className="shrink-0 border-t border-line bg-panel px-5 py-3 shadow-[0_-8px_16px_rgba(0,0,0,0.35)]">
          {pending ? (
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={act(onApprove)}
                disabled={busy}
                className="rounded-md bg-accent px-4 py-3 text-sm font-semibold uppercase tracking-wide text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Approve &amp; escalate
              </button>
              <button
                type="button"
                onClick={act(onReject)}
                disabled={busy}
                className="rounded-md border border-slate-500 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Reject (false positive)
              </button>
            </div>
          ) : (
            <div>
              <div className="mb-2 text-xs uppercase tracking-wide text-muted">
                Approved by {incident.operator ?? "operator"}
              </div>
              <EscalationTimeline steps={incident.escalation} gateLabel={gateLabel} />
            </div>
          )}
        </footer>
      </section>
    </div>
  );
}
