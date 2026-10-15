"use client";

import { useEffect, useState } from "react";

import { getReports } from "@/lib/api";
import type { DemoOutcome, ReportMeta, ReportsResponse } from "@/lib/types";

import { CmsHeader } from "./CameraGrid";
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
    <section className="flex flex-col gap-3 rounded-xl border border-line bg-panel p-4">
      <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
      {children}
    </section>
  );
}

function MetaLine({ meta, name }: { meta: ReportMeta; name: string }) {
  return (
    <div>
      <span className="text-slate-300">{name}</span>: commit {meta.commit.slice(0, 7)}, triggers {meta.triggers}, verifier{" "}
      {meta.verifier}
      {meta.model ? `, model ${meta.model}` : ""}
      {meta.threshold != null ? `, threshold ${meta.threshold}` : ""}, {new Date(meta.generated_at).toUTCString()}
    </div>
  );
}

export default function ResultsView() {
  const [data, setData] = useState<ReportsResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getReports()
      .then(setData)
      .catch(() => setFailed(true));
  }, []);

  const bench = data?.benchmark ?? null;
  const agg = bench?.test?.aggregate ?? null;
  const scale = data?.scale ?? null;
  const baseline = data?.baseline?.time_to_notice_s ?? null;
  const missing = data !== null && (!bench || !scale);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <CmsHeader title="Analysis" subtitle="How accurate, how fast and how far the system scales" />
      <main className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        {failed && <p className="text-sm text-warn">Could not load reports: the backend is not reachable.</p>}
        {!data && !failed && <p className="text-sm text-muted">Loading…</p>}
        {data && (
          <>
            {bench?.meta.verifier === "mock" && (
              <div role="alert" className="rounded-xl border border-warn bg-panel2 p-3 text-sm text-warn">
                Results use a mock AI verifier and are not valid evidence. Re-run the benchmark with a real verifier.
              </div>
            )}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <KpiTile
                label="Snatch → alert card"
                value={secs(agg?.detection_to_card_p50_s)}
                compare={baseline == null ? "baseline pending" : `baseline ${baseline} s`}
                note="median, from the snatch to the card on screen"
              />
              <KpiTile
                label="Detected"
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
                value={rate(agg?.false_per_hour_final)}
                note={agg ? `over ${agg.non_event_hours.toFixed(1)} h of normal footage` : "needs a test-set benchmark"}
              />
              <KpiTile
                label="False alarms filtered by AI"
                value={pct(agg?.ai_filter_rate)}
                note="share of Step 1 false triggers removed by Step 2"
              />
              <KpiTile
                label="Cameras per GPU"
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
                <code className="block overflow-x-auto whitespace-pre-wrap rounded bg-bg p-2 text-xs text-slate-300">
                  {data.generated_hint}
                </code>
              </Section>
            )}

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
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
                        <td className={`py-1.5 ${GOOD.includes(row.outcome) ? "text-ok" : "text-accent"}`}>
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
      {data && (
        <footer className="flex flex-col gap-1 border-t border-line bg-panel px-4 py-2 text-xs text-muted">
          {bench && <MetaLine meta={bench.meta} name="Benchmark" />}
          {scale && <MetaLine meta={scale.meta} name="Scale test" />}
          <div>Guard feedback rows: {data.feedback_rows}</div>
        </footer>
      )}
    </div>
  );
}
