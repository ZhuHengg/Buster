"use client";

import { useRef, useState } from "react";

import type { StreamSummary } from "@/lib/health";
import { STATUS_CHIP, STATUS_LABEL } from "@/lib/status";
import { useDismiss } from "@/lib/useDismiss";
import { STREAM_META } from "@/lib/stream";
import type { Incident } from "@/lib/types";

import Icon from "./Icon";

const MAX_INCIDENTS = 6;

const hhmmss = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { hour12: false });

/** Top-right button with counts; opens a dropdown of the newest incidents and the cameras with stream faults. */
export default function RecentEvents({
  incidents,
  summary,
  activeId,
  onOpen,
}: {
  incidents: Incident[];
  summary: StreamSummary;
  activeId: string | null;
  onOpen: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useDismiss(open, () => setOpen(false), wrapRef);

  const recent = incidents
    .filter((i) => i.status !== "CANDIDATE" && i.status !== "AI_REJECTED")
    .sort((a, b) => Date.parse(b.candidate.detected_at) - Date.parse(a.candidate.detected_at))
    .slice(0, MAX_INCIDENTS);
  const faults = summary.faults;
  const empty = recent.length === 0 && faults.length === 0;

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        className="flex cursor-pointer items-center gap-2 rounded-full border border-line-strong bg-panel px-3.5 py-1.5 text-xs font-semibold text-ink transition-colors hover:bg-panel2"
      >
        <Icon name="alert" size={14} className="text-brand-soft" />
        Events &amp; faults
        {recent.length > 0 && <span className="rounded-full bg-brand px-1.5 text-[11px] font-bold leading-5 text-white">{recent.length}</span>}
        {faults.length > 0 && <span className="rounded-full bg-warn-tint px-1.5 text-[11px] font-bold leading-5 text-warn">{faults.length}</span>}
        <Icon name="chevronDown" size={14} className={`text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <section
          aria-label="Recent events and stream faults"
          className="absolute right-0 top-full z-40 mt-2 max-h-[70vh] w-[340px] max-w-[90vw] overflow-y-auto rounded-[var(--r-lg)] border border-line-strong bg-[#1d1d20] p-2 shadow-[var(--shadow-pop)]"
        >
          {empty ? (
            <p className="px-3 py-4 text-center text-xs text-muted">Nothing needs attention.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {recent.map((inc) => {
                const v = inc.verification;
                return (
                  <li key={inc.id}>
                    <button
                      type="button"
                      onClick={() => {
                        onOpen(inc.id);
                        setOpen(false);
                      }}
                      aria-pressed={activeId === inc.id}
                      className={`flex w-full cursor-pointer items-center gap-3 rounded-[var(--r-md)] border px-3 py-2 text-left transition-colors hover:bg-white/5 ${
                        activeId === inc.id ? "border-brand" : "border-line"
                      }`}
                    >
                      <Icon name="alert" size={16} className="shrink-0 text-brand-soft" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold capitalize text-ink">
                          {v ? v.incident_type.replace("_", " ") : "Unverified event"}
                        </span>
                        <span className="mono-time block text-[11px] text-muted">
                          {hhmmss(inc.candidate.detected_at)} · {inc.camera_id}
                        </span>
                      </span>
                      <span
                        className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-semibold ${STATUS_CHIP[inc.status]}`}
                      >
                        {STATUS_LABEL[inc.status]}
                      </span>
                    </button>
                  </li>
                );
              })}
              {faults.map((f) => (
                <li key={f.id} className="flex items-center gap-3 rounded-[var(--r-md)] border border-line px-3 py-2">
                  <Icon name="alert" size={16} className="shrink-0 text-warn" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-ink">Stream {STREAM_META[f.state].label.toLowerCase()}</span>
                    <span className="mono-time block text-[11px] text-muted">{f.id}</span>
                  </span>
                  <span className="shrink-0 rounded-full bg-warn-tint px-2 py-0.5 text-[11px] font-semibold text-warn">Stream issue</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
