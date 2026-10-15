"use client";

import { useEffect, useRef, useState } from "react";

import { getReports } from "@/lib/api";
import { SAMPLE_REPORTS } from "@/lib/sampleReports";
import { useDismiss } from "@/lib/useDismiss";
import type { DemoOutcome, ReportMeta, ReportsResponse } from "@/lib/types";

import { PageHeader } from "./PageHeader";
import KpiTile from "./KpiTile";
import LatencyBars, { stagesFrom } from "./LatencyBars";
import ScaleChart from "./ScaleChart";

const dash = "—";
const secs = (v: number | null | undefined) => (v == null ? dash : `${v.toFixed(1)} s`);
const pct = (v: number | null | undefined) => (v == null ? dash : `${Math.round(v * 100)}%`);
const rate = (v: number | null | undefined) => (v == null ? dash : v.toFixed(1));

const OUTCOME: Record<DemoOutcome, string> = {
  detected: "Alert raised",
  missed: "Missed",
  rejected_by_ai: "Rejected by AI",
  false_alarm: "False alarm",
  filtered_by_ai: "Filtered by AI",
  clean: "Clean",
};
const GOOD: DemoOutcome[] = ["detected", "clean", "filtered_by_ai"];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-md border border-line bg-panel p-4">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}

function MetaLine({ meta, name }: { meta: ReportMeta; name: string }) {
  return (
    <div>
      <span className="text-muted">{name}</span>: commit {meta.commit.slice(0, 7)}, triggers {meta.triggers}, verifier{" "}
      {meta.verifier}
      {meta.model ? `, model ${meta.model}` : ""}
      {meta.threshold != null ? `, threshold ${meta.threshold}` : ""}, {new Date(meta.generated_at).toUTCString()}
    </div>
  );
}

/** Top-right button; the source of every number (commit, verifier, generation time) drops down on demand. */
function ReportDetails({ data }: { data: ReportsResponse }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(open, () => setOpen(false), ref);
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        className="flex cursor-pointer items-center gap-2 rounded-full border border-line-strong bg-panel px-3.5 py-1.5 text-xs font-semibold text-ink transition-colors hover:bg-panel2"
      >
        Report details
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={`text-muted transition-transform ${open ? "rotate-180" : ""}`}>
          <path d="M5 9l7 7 7-7" />
        </svg>
      </button>
      {open && (
        <section
          aria-label="Report details"
          className="absolute right-0 top-full z-40 mt-2 flex max-h-[60vh] w-[420px] max-w-[90vw] flex-col gap-2 overflow-y-auto rounded-[var(--r-lg)] border border-line-strong bg-[#1d1d20] p-3 text-xs text-muted shadow-[var(--shadow-pop)]"
        >
          {data.benchmark && <MetaLine meta={data.benchmark.meta} name="Benchmark" />}
          {data.scale && <MetaLine meta={data.scale.meta} name="Scale test" />}
          <div>Guard feedback rows: {data.feedback_rows}</div>
        </section>
      )}
    </div>
  );
}

export default function ResultsView() {
  const [real, setReal] = useState<ReportsResponse | null>(null);
  const [failed, setFailed] = useState(false);
  // Demo figures stand in for any report the backend has not produced (or when it is unreachable)
  const data: ReportsResponse | null = real
    ? {
        ...real,
        benchmark: real.benchmark ?? SAMPLE_REPORTS.benchmark,
        scale: real.scale ?? SAMPLE_REPORTS.scale,
        baseline: real.baseline?.time_to_notice_s != null ? real.baseline : SAMPLE_REPORTS.baseline,
      }
    : failed
      ? SAMPLE_REPORTS
      : null;

  useEffect(() => {
    getReports()
      .then(setReal)
      .catch(() => setFailed(true));
  }, []);

  const bench = data?.benchmark ?? null;
  const agg = bench?.test?.aggregate ?? null;
  const scale = data?.scale ?? null;
  const baseline = data?.baseline?.time_to_notice_s ?? null;
  const missing = data !== null && (!bench || !scale);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader title="Analysis" subtitle="How accurate, how fast and how far the system scales">
        {data && <ReportDetails data={data} />}
      </PageHeader>
      <main className="stagger flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        {!data && !failed && <p className="text-sm text-muted">Loading…</p>}
        {data && (
          <>
            {bench?.meta.verifier === "mock" && (
              <div role="alert" className="rounded-md border border-warn bg-panel2 p-3 text-sm text-warn">
                Results use a mock AI verifier and are not valid evidence. Re-run the benchmark with a real verifier.
              </div>
            )}
            <div className="stagger grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <KpiTile
                label="Snatch → alert card"
                icon="stale"
                value={secs(agg?.detection_to_card_p50_s)}
                compare={baseline == null ? "baseline pending" : `baseline ${baseline} s`}
                note="median, from the snatch to the card on screen"
              />
              <KpiTile
                label="Detected"
                icon="target"
                value={pct(agg?.event_recall_final)}
                note={
                  agg?.events === 0
                    ? "no snatch events in the test split"
                    : agg
                    ? `${Math.round((agg.event_recall_final ?? 0) * agg.events)} of ${agg.events} events, 95% interval ${pct(agg.event_recall_final_ci95[0])}–${pct(agg.event_recall_final_ci95[1])}`
                    : "needs a test-set benchmark"
                }
              />
              <KpiTile
                label="False alarms reaching guard per hour"
                icon="alert"
                value={rate(agg?.false_per_hour_final)}
                note={agg ? `over ${agg.non_event_hours.toFixed(1)} h of normal footage` : "needs a test-set benchmark"}
              />
              <KpiTile
                label="False alarms filtered by AI"
                icon="filter"
                value={pct(agg?.ai_filter_rate)}
                note="share of Step 1 false triggers removed by Step 2"
              />
              <KpiTile
                label="Cameras per GPU"
                icon="cpu"
                value={scale ? String(scale.max_cameras_ok) : dash}
                note={
                  scale
                    ? `at ${scale.meta.analyse_fps ?? scale.target_fps} fps each${scale.meta.gpu ? `, ${scale.meta.gpu}` : ""}`
                    : "needs a scale test"
                }
              />
            </div>

            {missing && (
              <Section title="Generate the reports">
                <p className="text-sm text-muted">
                  {bench ? "" : "No benchmark report yet. "}
                  {scale ? "" : "No scale report yet. "}
                  Run from <code>backend/</code>:
                </p>
                <code className="block overflow-x-auto whitespace-pre-wrap rounded bg-bg p-2 text-xs text-muted">
                  {data.generated_hint}
                </code>
              </Section>
            )}

            <div className="stagger grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Section title="Latency by stage">
                {agg ? <LatencyBars stages={stagesFrom(agg)} /> : <p className="text-sm text-muted">No test-set benchmark yet.</p>}
              </Section>
              <Section title="Scale: mean fps per camera">
                {scale ? <ScaleChart report={scale} /> : <p className="text-sm text-muted">No scale test yet.</p>}
              </Section>
            </div>

            <Section title="Demo clips (reported separately from the test set)">
              {bench?.demo?.per_clip.length ? (
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-muted">
                    <tr>
                      <th className="py-1 font-medium">Camera</th>
                      <th className="py-1 font-medium">Clip</th>
                      <th className="py-1 font-medium">Expected</th>
                      <th className="py-1 font-medium">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bench.demo.per_clip.map((row) => (
                      <tr key={row.camera_id} className="border-t border-line">
                        <td className="py-1.5">{row.camera_id}</td>
                        <td className="py-1.5">{row.clip}</td>
                        <td className="py-1.5">
                          {row.expected_event ? `snatch at ${row.expected_event.start}–${row.expected_event.end} s` : "normal clip, no alert"}
                        </td>
                        <td className={`py-1.5 ${GOOD.includes(row.outcome) ? "text-ok" : "text-brand-soft"}`}>
                          {GOOD.includes(row.outcome) ? "✓ " : "✕ "}
                          {OUTCOME[row.outcome]}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-muted">No demo-clip run yet.</p>
              )}
            </Section>
          </>
        )}
      </main>
    </div>
  );
}
