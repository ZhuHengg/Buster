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

/** Tailwind classes for the status chip. */
export const STATUS_CHIP: Record<IncidentStatus, string> = {
  CANDIDATE: "border-slate-500/60 bg-slate-500/10 text-slate-300",
  AI_REJECTED: "border-sky-500/50 bg-sky-500/10 text-sky-300",
  PENDING_REVIEW: "border-warn/60 bg-warn/10 text-warn",
  APPROVED: "border-orange-500/60 bg-orange-500/10 text-orange-300",
  REJECTED: "border-line bg-white/5 text-muted",
  ESCALATED: "border-accent/60 bg-accent/10 text-red-300",
};

export const seconds = (n: number | undefined): string => (n === undefined ? "—" : `${n.toFixed(1)} s`);
