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

const DONE: Status[] = ["completed", "sent"];
const ACTIVE: Status[] = ["ringing", "in_progress"];

/** One node on the timeline. Colour and icon change smoothly as the step moves along. */
function Node({ status }: { status: Status | "waiting" }) {
  const done = status === "completed" || status === "sent";
  const failed = status === "failed";
  const active = status === "ringing" || status === "in_progress";
  const tone = done
    ? "border-ok bg-ok text-slate-900"
    : failed
      ? "border-accent bg-accent text-white"
      : active
        ? "border-warn bg-warn/20 text-warn"
        : status === "queued"
          ? "border-line-strong bg-panel text-muted"
          : "border-line bg-panel text-muted";
  return (
    // key on status: the node pops each time the step changes state
    <span key={status} className={`step-pop relative z-10 flex h-7 w-7 items-center justify-center rounded-full border-2 transition-colors duration-500 ${tone}`} aria-hidden>
      {active && <span className="absolute inset-0 animate-ping rounded-full bg-warn/40" />}
      {done && (
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
          <path className="check-draw" d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
      )}
      {failed && (
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      )}
      {active && <span className="relative h-2 w-2 rounded-full bg-warn" />}
      {!done && !failed && !active && status === "queued" && <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />}
      {status === "skipped" && <span className="h-0.5 w-2.5 rounded bg-muted" />}
    </span>
  );
}

/** The line to the next node: fills left to right once this step is done, flows while it is running. */
function Track({ status }: { status: Status | "waiting" }) {
  const done = DONE.includes(status as Status);
  const active = ACTIVE.includes(status as Status);
  return (
    <span
      aria-hidden
      className="absolute left-[calc(50%+18px)] top-[12px] h-[3px] w-[calc(100%-36px)] overflow-hidden rounded-full bg-line"
    >
      <span
        className={`absolute inset-0 origin-left rounded-full bg-ok transition-transform duration-700 ease-out ${done ? "scale-x-100" : "scale-x-0"}`}
      />
      {active && <span className="track-flow absolute inset-0 rounded-full" />}
    </span>
  );
}

export default function EscalationTimeline({
  steps,
  gateLabel,
  compact = false,
}: {
  steps: EscalationStep[];
  gateLabel?: string;
  compact?: boolean; // tighter text, for the alert card
}) {
  const by = new Map<Channel, EscalationStep>(steps.map((s) => [s.channel, s]));
  // the order the system acts in: close the exit first, then tell the police by SMS, then phone them
  const rows: { channel: Channel; label: string }[] = [
    { channel: "gate_sms", label: gateLabel ? `${gateLabel} alert` : "Gate alert" },
    { channel: "police_sms", label: "Police SMS" },
    { channel: "police_call", label: "Police call" },
  ];
  return (
    <ol className="grid grid-cols-3" aria-label="Escalation progress">
      {rows.map(({ channel, label }, i) => {
        const step = by.get(channel);
        const status = step?.status ?? "waiting";
        return (
          <li key={channel} title={step?.detail ?? undefined} className="relative flex min-w-0 flex-col items-center gap-1.5 px-1 text-center">
            <Node status={status} />
            {i < rows.length - 1 && <Track status={status} />}
            <span className={`${compact ? "text-xs" : "text-sm"} w-full truncate font-medium text-ink`}>{label}</span>
            <span
              key={status}
              className={`fade-up text-[11px] font-medium ${
                status === "failed" ? "text-brand-soft" : DONE.includes(status as Status) ? "text-ok" : step ? "text-ink" : "text-muted"
              }`}
            >
              {step ? STATUS_TEXT[step.status] : "Waiting"}
            </span>
            {!compact && step?.detail && <span className="w-full truncate text-[11px] text-muted">{step.detail}</span>}
          </li>
        );
      })}
    </ol>
  );
}
