import type { BenchmarkAggregate } from "@/lib/types";

export interface Stage {
  label: string;
  p50: number | null;
  p90: number | null;
}

export function stagesFrom(a: BenchmarkAggregate): Stage[] {
  return [
    { label: "Detection (event → candidate)", p50: a.event_to_candidate_p50_s, p90: a.event_to_candidate_p90_s },
    { label: "Screening call", p50: a.step1_wall_p50_s, p90: a.step1_wall_p90_s },
    { label: "AI verification", p50: a.candidate_to_verified_p50_s, p90: a.candidate_to_verified_p90_s },
    { label: "Push to screen", p50: a.push_s, p90: a.push_s },
    { label: "Total, snatch → alert card", p50: a.detection_to_card_p50_s, p90: a.detection_to_card_p90_s },
  ];
}

const W = 640;
const LABEL_W = 210;
const BAR_H = 12;
const GAP = 2;
const ROW_H = 2 * BAR_H + GAP + 18;
const fmt = (v: number | null) => (v === null ? "—" : `${v.toFixed(1)} s`);

export default function LatencyBars({ stages }: { stages: Stage[] }) {
  const max = Math.max(1, ...stages.flatMap((s) => [s.p50 ?? 0, s.p90 ?? 0]));
  const plotW = W - LABEL_W - 64;
  const x = (v: number) => (v / max) * plotW;
  const height = stages.length * ROW_H + 8;
  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="flex items-center gap-4 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "linear-gradient(90deg,#c2410c,#ff9a52)" }} />
          median (p50)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "linear-gradient(90deg,#3f68b8,#8fc0ff)" }} />
          slow case (p90)
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-label="Latency per stage, p50 and p90, in seconds" className="w-full overflow-visible">
        <defs>
          <linearGradient id="lat-p50" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="#c2410c" />
            <stop offset="1" stopColor="#ff9a52" />
          </linearGradient>
          <linearGradient id="lat-p90" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="#3f68b8" />
            <stop offset="1" stopColor="#8fc0ff" />
          </linearGradient>
        </defs>
        <line x1={LABEL_W} x2={LABEL_W} y1={0} y2={height} stroke="var(--line)" strokeWidth={1} />
        {stages.map((s, i) => {
          const y = i * ROW_H + 4;
          const bars = [
            { name: "p50", v: s.p50, colour: "url(#lat-p50)", dy: 0 },
            { name: "p90", v: s.p90, colour: "url(#lat-p90)", dy: BAR_H + GAP },
          ];
          return (
            <g key={s.label} className="bar-row">
              <rect x={LABEL_W} y={y} width={plotW} height={2 * BAR_H + GAP} rx={5} fill="white" opacity={0.035} stroke="white" strokeOpacity={0.06} />
              <text x={LABEL_W - 10} y={y + BAR_H + 3} textAnchor="end" fontSize={12} fill="var(--muted)">
                {s.label}
              </text>
              {bars.map(({ name, v, colour, dy }) => (
                <g key={name}>
                  {v !== null && (
                    <g
                      className={`bar-grow bar ${name === "p50" ? "glow-orange" : "glow-blue"}`}
                      style={{ animationDelay: `${i * 90 + (dy ? 60 : 0)}ms` }}
                    >
                      <rect x={LABEL_W} y={y + dy} width={Math.max(2, x(v))} height={BAR_H} rx={5} fill={colour} fillOpacity={0.82}>
                        <title>{`${s.label} ${name}: ${fmt(v)}`}</title>
                      </rect>
                    </g>
                  )}
                  <text x={LABEL_W + (v === null ? 0 : Math.max(2, x(v))) + 6} y={y + dy + BAR_H - 2} fontSize={11} fill="var(--text)" className="label-in" style={{ animationDelay: `${i * 90 + 600}ms` }}>
                    {fmt(v)}
                  </text>
                </g>
              ))}
            </g>
          );
        })}
      </svg>
      <details className="text-xs text-muted">
        <summary className="cursor-pointer">Show as table</summary>
        <table className="mt-2 w-full text-left">
          <thead>
            <tr>
              <th className="py-1 font-medium">Stage</th>
              <th className="py-1 font-medium">p50</th>
              <th className="py-1 font-medium">p90</th>
            </tr>
          </thead>
          <tbody>
            {stages.map((s) => (
              <tr key={s.label} className="border-t border-line">
                <td className="py-1">{s.label}</td>
                <td className="py-1 tabular-nums">{fmt(s.p50)}</td>
                <td className="py-1 tabular-nums">{fmt(s.p90)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
