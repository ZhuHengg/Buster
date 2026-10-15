"use client";

import type { StreamSummary } from "@/lib/health";
import { STREAM_META } from "@/lib/stream";
import type { Incident } from "@/lib/types";

import CountUp from "./CountUp";
import Icon, { type IconName } from "./Icon";

type Tone = "neutral" | "ok" | "warn" | "crit";

const TONE: Record<Tone, { value: string; icon: string; dot: string }> = {
  neutral: { value: "text-ink", icon: "text-muted", dot: "bg-muted" },
  ok: { value: "text-ink", icon: "text-ok", dot: "bg-ok" },
  warn: { value: "text-warn", icon: "text-warn", dot: "bg-warn" },
  crit: { value: "text-brand-soft", icon: "text-brand-soft", dot: "bg-brand" },
};

function Indicator({
  icon,
  label,
  value,
  sub,
  title,
  tone,
  onClick,
}: {
  icon: IconName;
  label: string;
  value: string;
  sub: string;
  title?: string;
  tone: Tone;
  onClick?: () => void;
}) {
  const t = TONE[tone];
  const body = (
    <>
      <Icon name={icon} size={30} className={`shrink-0 ${t.icon}`} />
      <span className="min-w-0 text-left">
        <span className="flex items-baseline gap-2">
          <span className={`mono-time text-3xl font-bold leading-none ${t.value}`}>
            <CountUp value={value} />
          </span>
          <span className="truncate text-sm font-medium text-ink">{label}</span>
        </span>
        <span className="mt-1.5 flex items-center gap-1.5 text-xs text-muted">
          <span aria-hidden className={`h-2 w-2 shrink-0 rounded-full ${t.dot} ${tone === "crit" ? "pulse-ring" : ""}`} />
          <span className="truncate">{sub}</span>
        </span>
      </span>
    </>
  );
  const cls = "flex min-w-0 items-center gap-4 px-5 py-4";
  return onClick ? (
    <button type="button" onClick={onClick} title={title} className={`${cls} w-full cursor-pointer transition-colors hover:bg-white/5`}>
      {body}
    </button>
  ) : (
    <div title={title} className={cls}>
      {body}
    </div>
  );
}

export interface StatusStripProps {
  summary: StreamSummary;
  incidents: Incident[];
  onReview?: () => void;
}

/** One bar with four counters separated by dividers. */
export default function StatusStrip({ summary, incidents, onReview }: StatusStripProps) {
  const pending = incidents.filter((i) => i.status === "PENDING_REVIEW").length;
  const escalated = incidents.filter((i) => i.status === "ESCALATED" || i.status === "APPROVED").length;
  const connecting = summary.counts.CONNECTING;
  const cams = `/ ${summary.total} cameras`;
  const faultFull = summary.faults.map((f) => `${f.id} ${STREAM_META[f.state].label.toLowerCase()}`).join(", ");
  const total = `/ ${incidents.length} incidents`;

  return (
    <section
      aria-label="Operational summary"
      className="@container shrink-0 overflow-hidden rounded-[var(--r-lg)] border border-line bg-panel shadow-[var(--shadow-1)]"
    >
      <div className="stagger grid grid-cols-2 divide-line @[44rem]:grid-cols-4 @[44rem]:divide-x">
        <Indicator
          icon="camera"
          label="Live"
          value={String(summary.counts.LIVE)}
          sub={connecting > 0 ? `${cams} · ${connecting} connecting` : cams}
          tone={summary.counts.LIVE === summary.total && summary.total > 0 ? "ok" : "neutral"}
        />
        <Indicator
          icon="nosignal"
          label="Stream issues"
          value={String(summary.faults.length)}
          sub={cams}
          title={summary.faults.length > 0 ? faultFull : undefined}
          tone={summary.faults.length > 0 ? "warn" : "neutral"}
        />
        <Indicator
          icon="bell"
          label="Awaiting review"
          value={String(pending)}
          sub={total}
          title={pending > 0 ? "Open the oldest alert" : undefined}
          tone={pending > 0 ? "crit" : "neutral"}
          onClick={pending > 0 ? onReview : undefined}
        />
        <Indicator icon="shield" label="Escalated" value={String(escalated)} sub={total} tone={escalated > 0 ? "crit" : "neutral"} />
      </div>
    </section>
  );
}
