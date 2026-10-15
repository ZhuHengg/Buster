"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useCms } from "@/lib/cms";

import Icon, { type IconName } from "./Icon";

// Only modules that have a working page are listed. Camera Management and System Health / Settings
// have no implementation yet, so they are deliberately absent rather than shown as dead links.
const NAV: { href: string; label: string; icon: IconName; hint: string }[] = [
  { href: "/", label: "Live Monitoring", icon: "live", hint: "All cameras and alerts" },
  { href: "/incidents", label: "Incident Management", icon: "incidents", hint: "Every alert and its outcome" },
  { href: "/trace", label: "Trace & Investigation", icon: "trace", hint: "Follow a suspect on the map" },
  { href: "/results", label: "Analytics & Reports", icon: "analytics", hint: "Accuracy, speed and scale results" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { state } = useCms();
  const pending = Object.values(state.incidents).filter((i) => i.status === "PENDING_REVIEW").length;
  return (
    <nav
      aria-label="Modules"
      className="flex w-14 shrink-0 flex-col gap-0.5 border-r border-line bg-panel py-2 lg:w-64"
    >
      <div className="hidden px-4 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wider text-muted lg:block">
        Modules
      </div>
      {NAV.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        const badge = item.href === "/incidents" && pending > 0 ? pending : 0;
        return (
          <Link
            key={item.href}
            href={item.href}
            title={`${item.label}: ${item.hint}`}
            aria-current={active ? "page" : undefined}
            className={`relative mx-1.5 flex items-center gap-3 rounded-[var(--r-md)] px-2.5 py-2.5 text-[13px] transition-colors lg:mx-2 ${
              active
                ? "bg-brand-tint font-semibold text-ink"
                : "font-medium text-muted hover:bg-panel2 hover:text-ink"
            }`}
          >
            <span
              aria-hidden
              className={`absolute -left-1.5 bottom-1.5 top-1.5 w-[3px] rounded-r lg:-left-2 ${active ? "bg-brand" : "bg-transparent"}`}
            />
            <Icon name={item.icon} size={18} className={active ? "text-brand-soft" : ""} />
            <span className="hidden flex-1 truncate lg:inline">{item.label}</span>
            {badge > 0 && (
              <span className="hidden min-w-5 rounded-full bg-brand px-1.5 text-center text-[11px] font-bold leading-5 text-white lg:inline">
                {badge}
                <span className="sr-only"> awaiting review</span>
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
