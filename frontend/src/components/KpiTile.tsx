import type { ReactNode } from "react";

import CountUp from "./CountUp";
import Icon, { type IconName } from "./Icon";

export interface KpiTileProps {
  label: string;
  /** Already formatted; "—" when the report does not have the number. */
  value: string;
  icon?: IconName;
  note?: ReactNode;
  /** Shown under the value, e.g. the baseline to compare against. */
  compare?: ReactNode;
}

export default function KpiTile({ label, value, icon, note, compare }: KpiTileProps) {
  return (
    <div data-kpi className="flex flex-col gap-1 lift rounded-[var(--r-lg)] border border-line bg-panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="text-xs text-muted">{label}</div>
        {icon && (
          <span aria-hidden className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-tint text-brand-soft">
            <Icon name={icon} size={18} />
          </span>
        )}
      </div>
      <div className="text-3xl font-semibold text-ink">
        <CountUp value={value} />
      </div>
      {compare ? <div className="text-xs text-muted">{compare}</div> : null}
      {note ? <div className="text-xs text-muted">{note}</div> : null}
    </div>
  );
}
