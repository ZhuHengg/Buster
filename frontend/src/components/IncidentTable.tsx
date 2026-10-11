"use client";

import { useMemo, useState } from "react";

import { seconds, STATUS_CHIP, STATUS_LABEL, STATUS_ORDER } from "@/lib/status";
import type { Incident, IncidentStatus } from "@/lib/types";

export interface IncidentTableProps {
  incidents: Incident[];
  selectedId?: string | null;
  onSelect?: (incident: Incident) => void;
}

type Filter = "ALL" | IncidentStatus;

const typeLabel = (i: Incident) =>
  i.verification
    ? i.verification.incident_type.replace("_", " ").replace(/^./, (c) => c.toUpperCase())
    : "Unverified";

export function StatusChip({ status }: { status: IncidentStatus }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded border px-2 py-0.5 text-xs font-medium ${STATUS_CHIP[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}

export default function IncidentTable({ incidents, selectedId, onSelect }: IncidentTableProps) {
  const [filter, setFilter] = useState<Filter>("ALL");

  const sorted = useMemo(
    () => [...incidents].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)),
    [incidents],
  );
  const counts = useMemo(() => {
    const c = new Map<Filter, number>([["ALL", incidents.length]]);
    for (const i of incidents) c.set(i.status, (c.get(i.status) ?? 0) + 1);
    return c;
  }, [incidents]);
  const rows = filter === "ALL" ? sorted : sorted.filter((i) => i.status === filter);
  const filters: { key: Filter; label: string }[] = [
    { key: "ALL", label: "All" },
    ...STATUS_ORDER.map((s) => ({ key: s as Filter, label: STATUS_LABEL[s] })),
  ];

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
        {filters.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            aria-pressed={filter === key}
            onClick={() => setFilter(key)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
              filter === key
                ? "border-slate-300 bg-slate-100 text-slate-900"
                : "border-line bg-panel2 text-slate-300 hover:border-slate-500"
            }`}
          >
            {label} <span className="mono-time opacity-70">{counts.get(key) ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="min-h-0 overflow-auto rounded-md border border-line">
        <table className="w-full min-w-[860px] border-collapse text-left text-sm">
          <thead className="sticky top-0 bg-panel text-xs uppercase tracking-wide text-muted">
            <tr>
              {["Time", "Incident", "Camera", "Type", "Status", "Operator", "Detected", "AI verdict", "Call placed"].map(
                (h) => (
                  <th key={h} className="border-b border-line px-3 py-2 font-medium">
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-8 text-center text-muted">
                  No incidents
                </td>
              </tr>
            )}
            {rows.map((i) => {
              const selected = i.id === selectedId;
              return (
                <tr
                  key={i.id}
                  aria-selected={selected}
                  tabIndex={0}
                  onClick={() => onSelect?.(i)}
                  onKeyDown={(e) => e.key === "Enter" && onSelect?.(i)}
                  className={`cursor-pointer border-b border-line/60 outline-none transition hover:bg-white/5 focus-visible:bg-white/5 ${
                    selected ? "bg-white/10" : ""
                  }`}
                >
                  <td className="mono-time whitespace-nowrap px-3 py-2 text-slate-300">
                    {new Date(i.created_at).toLocaleTimeString("en-GB", { hour12: false })}
                  </td>
                  <td className="mono-time whitespace-nowrap px-3 py-2">{i.id}</td>
                  <td className="whitespace-nowrap px-3 py-2">{i.camera_id}</td>
                  <td className="whitespace-nowrap px-3 py-2">{typeLabel(i)}</td>
                  <td className="px-3 py-2">
                    <StatusChip status={i.status} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">{i.operator ?? "—"}</td>
                  <td className="mono-time px-3 py-2 text-slate-300">{seconds(i.metrics.candidate_s)}</td>
                  <td className="mono-time px-3 py-2 text-slate-300">{seconds(i.metrics.verified_s)}</td>
                  <td className="mono-time px-3 py-2 text-slate-300">{seconds(i.metrics.call_placed_s)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
