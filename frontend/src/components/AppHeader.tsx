"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { OPERATOR_NAME, OPERATOR_ROLE, TOWNSHIP_NAME } from "@/lib/config";
import { useCms } from "@/lib/cms";
import { summarizeStreams } from "@/lib/health";

import Icon from "./Icon";
import Logo from "./Logo";

function useNow(ms = 1000): number {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const id = setInterval(tick, ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

const hhmmss = (t: number) => new Date(t).toLocaleTimeString("en-GB", { hour12: false });

export default function AppHeader() {
  const { state, connected, cameras, streams, lastSyncAt } = useCms();
  const now = useNow();
  const pending = Object.values(state.incidents).filter((i) => i.status === "PENDING_REVIEW").length;
  const summary = cameras ? summarizeStreams(cameras, streams) : null;

  // The wording only claims what was measured: backend link first, then stream faults.
  let health: { text: string; tone: string; icon: "check" | "alert" | "offline" };
  if (!connected) {
    health = { text: "Backend link lost: reconnecting", tone: "bg-crit-tint text-crit", icon: "offline" };
  } else if (summary && summary.faults.length > 0) {
    const n = summary.faults.length;
    health = { text: `Degraded: ${n} stream ${n === 1 ? "issue" : "issues"}`, tone: "bg-warn-tint text-warn", icon: "alert" };
  } else if (summary && summary.measured === summary.total && summary.total > 0 && summary.counts.LIVE === summary.total) {
    health = { text: "All streams live", tone: "bg-ok-tint text-ok", icon: "check" };
  } else {
    health = { text: "Backend connected", tone: "bg-ok-tint text-ok", icon: "check" };
  }

  return (
    <header
      className="flex h-[var(--header-h)] shrink-0 items-center gap-4 border-b border-line bg-panel px-4"
      style={{ boxShadow: "inset 0 3px 0 var(--brand)" }}
    >
      <Link href="/" className="flex shrink-0 items-center gap-3 pt-[3px]" aria-label="Buster Security Operations Centre, home">
        <Logo />
        <span aria-hidden className="hidden h-6 w-px bg-line-strong sm:block" />
        <span className="hidden text-sm font-semibold text-ink sm:inline">Security Operations Centre</span>
      </Link>

      <div className="ml-auto flex min-w-0 items-center gap-2 pt-[3px] text-xs">
        <span
          className="hidden items-center gap-1.5 rounded-[var(--r-md)] border border-line px-2.5 py-1.5 font-medium text-ink md:flex"
          title="Site"
        >
          <Icon name="building" size={14} className="text-muted" />
          <span className="sr-only">Site: </span>
          {TOWNSHIP_NAME}
        </span>

        {/* shown only when something is wrong; a healthy system needs no badge */}
        {health.icon !== "check" && (
          <span role="status" className={`flex items-center gap-1.5 rounded-[var(--r-md)] px-2.5 py-1.5 font-semibold ${health.tone}`}>
            <Icon name={health.icon} size={14} />
            <span className="hidden sm:inline">System health: </span>
            {health.text}
          </span>
        )}

        <span
          className="mono-time hidden text-muted xl:inline"
          title="Last message received from the monitoring backend"
        >
          Last update {lastSyncAt && now ? hhmmss(lastSyncAt) : "—"}
        </span>

        <Link
          href="/incidents"
          className="relative flex h-8 w-8 items-center justify-center rounded-[var(--r-md)] border border-line text-ink hover:bg-panel2"
          aria-label={pending > 0 ? `${pending} incidents awaiting review` : "No incidents awaiting review"}
          title="Incidents awaiting review"
        >
          <Icon name="bell" size={16} />
          {pending > 0 && (
            <span className="absolute -right-1.5 -top-1.5 min-w-4 rounded-full bg-brand px-1 text-center text-[10px] font-bold leading-4 text-white pulse-ring">
              {pending}
            </span>
          )}
        </Link>

        <span className="flex items-center gap-2 border-l border-line pl-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand text-white">
            <Icon name="user" size={16} />
          </span>
          <span className="hidden leading-tight lg:block">
            <span className="block font-semibold text-ink">{OPERATOR_NAME}</span>
            <span className="block text-muted">{OPERATOR_ROLE}</span>
          </span>
        </span>
      </div>
    </header>
  );
}
