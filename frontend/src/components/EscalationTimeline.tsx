import type { EscalationStep } from "@/lib/types";

type Channel = EscalationStep["channel"];
type Status = EscalationStep["status"];

const STATUS_TEXT: Record<Status, string> = {
  queued: "Queued",
  ringing: "Ringing…",
  in_progress: "In progress",
  completed: "Completed",
  sent: "Sent",
  failed: "Failed",
  skipped: "Skipped",
};

function Icon({ status }: { status: Status | "waiting" }) {
  const base = "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-bold";
  switch (status) {
    case "completed":
    case "sent":
      return (
        <span className={`${base} border-ok bg-ok/15 text-ok`} aria-hidden>
          ✓
        </span>
      );
    case "failed":
      return (
        <span className={`${base} border-accent bg-accent/15 text-accent`} aria-hidden>
          ✕
        </span>
      );
    case "ringing":
    case "in_progress":
      return (
        <span className={`${base} rec-dot border-warn bg-warn/15 text-warn`} aria-hidden>
          ●
        </span>
      );
    case "queued":
      return (
        <span className={`${base} border-slate-500 text-slate-300`} aria-hidden>
          …
        </span>
      );
    case "skipped":
      return (
        <span className={`${base} border-line text-muted`} aria-hidden>
          –
        </span>
      );
    default:
      return (
        <span className={`${base} border-line text-muted`} aria-hidden>
          ○
        </span>
      );
  }
}

export default function EscalationTimeline({
  steps,
  gateLabel,
  compact = false,
}: {
  steps: EscalationStep[];
  gateLabel?: string;
  compact?: boolean; // three columns, for tight spaces
}) {
  const by = new Map<Channel, EscalationStep>(steps.map((s) => [s.channel, s]));
  const rows: { channel: Channel; label: string }[] = [
    { channel: "police_call", label: "Police call" },
    { channel: "police_sms", label: "Police SMS" },
    { channel: "gate_sms", label: gateLabel ? `${gateLabel} alert` : "Gate alert" },
  ];
  if (compact) {
    return (
      <ol className="grid grid-cols-3 gap-2" aria-label="Escalation progress">
        {rows.map(({ channel, label }) => {
          const step = by.get(channel);
          return (
            <li
              key={channel}
              title={step?.detail ?? undefined}
              className="flex min-w-0 flex-col gap-1.5 rounded-xl border border-line bg-panel2 px-2.5 py-2"
            >
              <div className="flex items-center gap-2">
                <Icon status={step?.status ?? "waiting"} />
                <span className="truncate text-sm font-medium text-slate-100">{label}</span>
              </div>
              <span
                className={`text-xs font-medium ${step?.status === "failed" ? "text-accent" : step ? "text-slate-200" : "text-muted"}`}
              >
                {step ? STATUS_TEXT[step.status] : "Waiting"}
              </span>
            </li>
          );
        })}
      </ol>
    );
  }
  return (
    <ol className="flex flex-col gap-2" aria-label="Escalation progress">
      {rows.map(({ channel, label }) => {
        const step = by.get(channel);
        return (
          <li key={channel} className="flex items-center gap-3 rounded-xl border border-line bg-panel2 px-3 py-2">
            <Icon status={step?.status ?? "waiting"} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-slate-100">{label}</div>
              {step?.detail && <div className="truncate text-xs text-muted">{step.detail}</div>}
            </div>
            <span
              className={`text-xs font-medium ${step?.status === "failed" ? "text-accent" : step ? "text-slate-200" : "text-muted"}`}
            >
              {step ? STATUS_TEXT[step.status] : "Waiting"}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
