import type { ReactNode } from "react";

export interface KpiTileProps {
  label: string;
  /** Already formatted; "—" when the report does not have the number. */
  value: string;
  note?: ReactNode;
  /** Shown under the value, e.g. the baseline to compare against. */
  compare?: ReactNode;
}

export default function KpiTile({ label, value, note, compare }: KpiTileProps) {
  return (
    <div data-kpi className="flex flex-col gap-1 rounded-md border border-line bg-panel p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-3xl font-semibold text-slate-100">{value}</div>
      {compare ? <div className="text-xs text-slate-300">{compare}</div> : null}
      {note ? <div className="text-xs text-muted">{note}</div> : null}
    </div>
  );
}
