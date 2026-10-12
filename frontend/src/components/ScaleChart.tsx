import type { ScaleReport, ScaleRow } from "@/lib/types";

const W = 640;
const H = 260;
const M = { l: 44, r: 24, t: 20, b: 36 };
const CRITICAL = "#d03b3b"; // status palette: the point where the GPU stopped keeping up

type Plotted = ScaleRow & { fps_mean: number };

export default function ScaleChart({ report }: { report: ScaleReport }) {
  const rows = report.rows;
  const plotted = rows.filter((r): r is Plotted => r.fps_mean !== null);
  const maxN = Math.max(1, ...rows.map((r) => r.n));
  const maxY = Math.max(report.target_fps * 1.2, ...plotted.map((r) => r.fps_mean), 1);
  const x = (n: number) => M.l + (n / maxN) * (W - M.l - M.r);
  const y = (v: number) => H - M.b - (v / maxY) * (H - M.t - M.b);
  // labels sit under their point; near the right edge they end at the point instead of running off the chart
  const anchor = (n: number) => (x(n) > W - 90 ? "end" : x(n) < M.l + 60 ? "start" : "middle");
  const lastOk = [...plotted].reverse().find((r) => r.ok);
  const stopped = plotted.find((r) => !r.ok);
  const ticks = [0, maxY / 2, maxY].map((v) => Math.round(v));
  const path = plotted.map((r, i) => `${i === 0 ? "M" : "L"}${x(r.n).toFixed(1)},${y(r.fps_mean).toFixed(1)}`).join(" ");
  return (
    <figure className="flex flex-col gap-2">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Mean analysis fps per camera against number of cameras" className="w-full">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} />
            <text x={M.l - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--muted)">
              {t}
            </text>
          </g>
        ))}
        {rows.map((r) => (
          <text key={r.n} x={x(r.n)} y={H - M.b + 18} textAnchor="middle" fontSize={11} fill="var(--muted)">
            {r.n}
          </text>
        ))}
        <text x={(M.l + W - M.r) / 2} y={H - 4} textAnchor="middle" fontSize={11} fill="var(--muted)">
          cameras running at once
        </text>
        <line
          x1={M.l}
          x2={W - M.r}
          y1={y(report.target_fps)}
          y2={y(report.target_fps)}
          stroke="var(--muted)"
          strokeWidth={1}
          strokeDasharray="4 4"
        />
        <text x={W - M.r} y={y(report.target_fps) - 5} textAnchor="end" fontSize={11} fill="var(--muted)">
          {`target ${report.target_fps} fps`}
        </text>
        {path && <path d={path} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />}
        {plotted.map((r) => (
          <circle
            key={r.n}
            cx={x(r.n)}
            cy={y(r.fps_mean)}
            r={r.n === lastOk?.n ? 6 : 4}
            fill={r.ok ? "var(--series-1)" : CRITICAL}
            stroke="var(--panel)"
            strokeWidth={2}
          >
            <title>{`${r.n} cameras: ${r.fps_mean.toFixed(1)} fps mean, ${r.fps_min?.toFixed(1)} min, p90 lag ${r.lag_p90_s?.toFixed(2)} s, ${r.gpu_mem_gb?.toFixed(1)} GB GPU`}</title>
          </circle>
        ))}
        {lastOk && (
          <text x={x(lastOk.n)} y={y(lastOk.fps_mean) + 24} textAnchor={anchor(lastOk.n)} fontSize={12} fontWeight={600} fill="var(--text)">
            {`${lastOk.n} ${lastOk.n === 1 ? "camera" : "cameras"} OK`}
          </text>
        )}
        {stopped && (
          <text x={x(stopped.n)} y={y(stopped.fps_mean) + 24} textAnchor={anchor(stopped.n)} fontSize={12} fill="var(--text)">
            {`✕ stopped at ${stopped.n}`}
          </text>
        )}
      </svg>
      {report.stopped_reason ? <p className="text-xs text-muted">{report.stopped_reason}</p> : null}
      <details className="text-xs text-muted">
        <summary className="cursor-pointer">Show as table</summary>
        <table className="mt-2 w-full text-left">
          <thead>
            <tr>
              {["Cameras", "Mean fps", "Min fps", "p90 lag", "GPU memory", "Result"].map((h) => (
                <th key={h} className="py-1 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.n} className="border-t border-line tabular-nums">
                <td className="py-1">{r.n}</td>
                <td className="py-1">{r.fps_mean?.toFixed(1) ?? "—"}</td>
                <td className="py-1">{r.fps_min?.toFixed(1) ?? "—"}</td>
                <td className="py-1">{r.lag_p90_s === null ? "—" : `${r.lag_p90_s.toFixed(2)} s`}</td>
                <td className="py-1">{r.gpu_mem_gb === null ? "—" : `${r.gpu_mem_gb.toFixed(1)} GB`}</td>
                <td className="py-1">{r.ok ? "OK" : r.oom ? "out of memory" : "stopped"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
