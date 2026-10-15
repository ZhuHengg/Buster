"use client";

import { useMemo, useState } from "react";

import { seconds, STATUS_CHIP, STATUS_FILTER, STATUS_LABEL, STATUS_ORDER } from "@/lib/status";
import type { Incident, IncidentStatus } from "@/lib/types";

export interface IncidentTableProps {
  incidents: Incident[];
  selectedId?: string | null;
  onSelect?: (incident: Incident) => void;
  /** When given, every row gets a remove button (with a confirmation step). */
  onRemove?: (incident: Incident) => void;
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

export default function IncidentTable({ incidents, selectedId, onSelect, onRemove }: IncidentTableProps) {
  const [filter, setFilter] = useState<Filter>("ALL");
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const columns = onRemove ? 10 : 9;

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
  // statuses with no incidents are left out (the selected one stays so it can be switched off)
  const filters: { key: Filter; label: string }[] = [
    { key: "ALL", label: "All" },
    ...STATUS_ORDER.filter((s) => (counts.get(s) ?? 0) > 0 || s === filter).map((s) => ({ key: s as Filter, label: STATUS_LABEL[s] })),
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
            className={`cursor-pointer rounded-full border px-3 py-1 text-xs font-semibold transition ${
              key === "ALL"
                ? filter === key
                  ? "border-ink bg-white/15 text-ink"
                  : "border-transparent bg-white/10 text-muted hover:brightness-125"
                : filter === key
                  ? STATUS_FILTER[key].active
                  : STATUS_FILTER[key].idle
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
              {onRemove && (
                <th className="border-b border-line px-3 py-2 font-medium">
                  <span className="sr-only">Remove</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={columns} className="px-3 py-8 text-center text-muted">
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
                    selected ? "bg-white/5" : ""
                  }`}
                >
                  <td className="mono-time whitespace-nowrap px-3 py-2 text-muted">
                    {new Date(i.created_at).toLocaleTimeString("en-GB", { hour12: false })}
                  </td>
                  <td className="mono-time whitespace-nowrap px-3 py-2">{i.id}</td>
                  <td className="whitespace-nowrap px-3 py-2">{i.camera_id}</td>
                  <td className="whitespace-nowrap px-3 py-2">{typeLabel(i)}</td>
                  <td className="px-3 py-2">
                    <StatusChip status={i.status} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">{i.operator ?? "—"}</td>
                  <td className="mono-time px-3 py-2 text-muted">{seconds(i.metrics.candidate_s)}</td>
                  <td className="mono-time px-3 py-2 text-muted">{seconds(i.metrics.verified_s)}</td>
                  <td className="mono-time px-3 py-2 text-muted">{seconds(i.metrics.call_placed_s)}</td>
                  {onRemove && (
                    <td className="whitespace-nowrap px-3 py-2 text-right" onClick={(e) => e.stopPropagation()}>
                      {confirmId === i.id ? (
                        <span className="inline-flex items-center gap-1.5">
                          <button
                            type="button"
                            aria-label={`Confirm remove ${i.id}`}
                            className="rounded border border-accent/70 bg-accent/15 px-2 py-0.5 text-xs font-medium text-brand-soft hover:bg-accent/30"
                            onClick={() => {
                              setConfirmId(null);
                              onRemove(i);
                            }}
                          >
                            Remove
                          </button>
                          <button
                            type="button"
                            className="rounded border border-line px-2 py-0.5 text-xs text-muted hover:border-line-strong"
                            onClick={() => setConfirmId(null)}
                          >
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          aria-label={`Remove ${i.id}`}
                          title="Remove from the log"
                          className="rounded px-1.5 py-0.5 text-base leading-none text-muted hover:bg-white/5 hover:text-brand-soft"
                          onClick={() => setConfirmId(i.id)}
                        >
                          ×
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
