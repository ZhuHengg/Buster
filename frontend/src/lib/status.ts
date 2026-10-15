import type { IncidentStatus } from "./types";

export const STATUS_ORDER: IncidentStatus[] = [
  "PENDING_REVIEW",
  "ESCALATED",
  "APPROVED",
  "REJECTED",
  "AI_REJECTED",
  "CANDIDATE",
];

export const STATUS_LABEL: Record<IncidentStatus, string> = {
  CANDIDATE: "Candidate",
  AI_REJECTED: "AI rejected",
  PENDING_REVIEW: "Pending review",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  ESCALATED: "Escalated",
};

/** One colour per status so rows and filters read at a glance: amber waiting, red escalated, green approved, blue AI-filtered, grey closed. */
export const STATUS_CHIP: Record<IncidentStatus, string> = {
  CANDIDATE: "border-line-strong bg-neutral-tint text-neutral",
  AI_REJECTED: "border-info/50 bg-info-tint text-info",
  PENDING_REVIEW: "border-warn/60 bg-warn-tint text-warn",
  APPROVED: "border-ok/50 bg-ok-tint text-ok",
  REJECTED: "border-line-strong bg-panel2 text-muted",
  ESCALATED: "border-crit/60 bg-crit-tint text-crit",
};

/** Filter pills above the incident table: always filled with the status colour (like the health pill); the selected one also gets an outline. */
export const STATUS_FILTER: Record<IncidentStatus, { idle: string; active: string }> = {
  PENDING_REVIEW: { idle: "border-transparent bg-warn-tint text-warn hover:brightness-125", active: "border-warn bg-warn-tint text-warn" },
  ESCALATED: { idle: "border-transparent bg-crit-tint text-crit hover:brightness-125", active: "border-crit bg-crit-tint text-crit" },
  APPROVED: { idle: "border-transparent bg-ok-tint text-ok hover:brightness-125", active: "border-ok bg-ok-tint text-ok" },
  REJECTED: { idle: "border-transparent bg-white/10 text-muted hover:brightness-125", active: "border-muted bg-white/10 text-ink" },
  AI_REJECTED: { idle: "border-transparent bg-info-tint text-info hover:brightness-125", active: "border-info bg-info-tint text-info" },
  CANDIDATE: { idle: "border-transparent bg-white/10 text-muted hover:brightness-125", active: "border-muted bg-white/10 text-ink" },
};

export const seconds = (n: number | undefined): string => (n === undefined ? "—" : `${n.toFixed(1)} s`);
