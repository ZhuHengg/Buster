"use client";

import { clipUrl, snapshotUrl } from "@/lib/api";
import type { CameraConfig, Incident } from "@/lib/types";

import EscalationTimeline from "./EscalationTimeline";
import { StatusChip } from "./IncidentTable";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3 border-b border-line/60 py-1.5 text-sm last:border-b-0">
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-ink">{children}</dd>
    </div>
  );
}

export default function IncidentDetail({ incident, camera }: { incident: Incident; camera?: CameraConfig }) {
  const v = incident.verification;
  const escalated = incident.escalation.length > 0;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="mono-time text-sm text-ink">{incident.id}</div>
          <div className="text-xs text-muted">
            {incident.camera_id}
            {camera ? ` · ${camera.name}` : ""}
          </div>
        </div>
        <StatusChip status={incident.status} />
      </div>

      <video
        key={incident.id}
        src={clipUrl(incident.clip_file, incident.clip_start, incident.clip_end)}
        className="aspect-video w-full rounded-md border border-line bg-black object-contain"
        muted
        controls
        playsInline
      />

      {incident.snapshot_files.length > 0 && (
        <div className="flex gap-2">
          {incident.snapshot_files.map((file, i) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={file}
              src={snapshotUrl(file)}
              alt={`Suspect snapshot ${i + 1}`}
              className="h-20 rounded-md border border-line bg-black object-contain"
            />
          ))}
        </div>
      )}

      <dl className="rounded-md border border-line bg-panel2 px-3 py-1">
        {v ? (
          <>
            <Field label="AI verdict">
              {v.is_incident ? "Incident confirmed" : "Not an incident"} ·{" "}
              <span className="mono-time">{Math.round(v.confidence * 100)}%</span>
            </Field>
            <Field label="Summary">{v.summary}</Field>
            {v.suspects.length > 0 && <Field label="Suspects">{v.suspects.map((s) => s.description).join("; ")}</Field>}
            {v.vehicle && (
              <Field label="Vehicle">
                {v.vehicle.colour} {v.vehicle.type}
                {v.vehicle.plate_visible && v.vehicle.plate_text ? `, plate ${v.vehicle.plate_text}` : ""}
              </Field>
            )}
            {v.victim && <Field label="Victim">{v.victim.description}</Field>}
          </>
        ) : (
          <Field label="AI verdict">{incident.verification_error ?? "No AI verification"}</Field>
        )}
        <Field label="Escape">
          {[incident.escape_direction, incident.escape_exit].filter(Boolean).join(" → ") || "Unknown"}
        </Field>
        {incident.operator && <Field label="Decided by">{incident.operator}</Field>}
      </dl>

      {escalated && (
        <div>
          <div className="mb-2 text-xs uppercase tracking-wide text-muted">Escalation</div>
          <EscalationTimeline steps={incident.escalation} gateLabel={incident.escape_exit ?? undefined} />
        </div>
      )}
    </div>
  );
}
