"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ICON = { fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" } as const;

const NAV = [
  {
    href: "/",
    label: "Live",
    hint: "Live monitoring: all cameras and alerts",
    icon: (
      <svg viewBox="0 0 24 24" {...ICON} aria-hidden>
        <rect x="3" y="3" width="7.5" height="7.5" rx="2" />
        <rect x="13.5" y="3" width="7.5" height="7.5" rx="2" />
        <rect x="3" y="13.5" width="7.5" height="7.5" rx="2" />
        <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2" />
      </svg>
    ),
  },
  {
    href: "/trace",
    label: "Trace",
    hint: "Live trace: follow a suspect on the map",
    icon: (
      <svg viewBox="0 0 24 24" {...ICON} aria-hidden>
        <path d="M12 21s-7-5.6-7-11a7 7 0 0 1 14 0c0 5.4-7 11-7 11z" />
        <circle cx="12" cy="10" r="2.6" />
      </svg>
    ),
  },
  {
    href: "/incidents",
    label: "Incidents",
    hint: "Incident log: every alert and its outcome",
    icon: (
      <svg viewBox="0 0 24 24" {...ICON} aria-hidden>
        <path d="M12 3.5 2.8 19.5a1 1 0 0 0 .9 1.5h16.6a1 1 0 0 0 .9-1.5z" />
        <path d="M12 10v4.5M12 17.6v.01" />
      </svg>
    ),
  },
  {
    href: "/results",
    label: "Analysis",
    hint: "Analysis: accuracy, speed and scale results",
    icon: (
      <svg viewBox="0 0 24 24" {...ICON} aria-hidden>
        <path d="M4 20V10M10 20V4M16 20v-7M21 20H3" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Main"
      className="flex w-[88px] shrink-0 flex-col items-center gap-2 rounded-2xl border border-line bg-shell px-2 py-4 shadow-[0_8px_30px_rgba(0,0,0,0.35)]"
    >
      <Link href="/" aria-label="Central Monitoring System" className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-white">
        <svg viewBox="0 0 24 24" width="22" height="22" {...ICON} aria-hidden>
          <path d="M12 3 4 6v5.5c0 4.6 3.3 8.3 8 9.5 4.7-1.2 8-4.9 8-9.5V6z" />
          <circle cx="12" cy="11" r="2.4" />
        </svg>
      </Link>
      {NAV.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            title={item.hint}
            aria-current={active ? "page" : undefined}
            className={`group flex w-full flex-col items-center gap-1 rounded-xl px-1 py-2.5 text-[11px] font-medium transition-colors ${
              active ? "bg-white/10 text-white" : "text-muted hover:bg-white/5 hover:text-slate-100"
            }`}
          >
            <span
              className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors [&>svg]:h-5 [&>svg]:w-5 ${
                active ? "bg-accent text-white" : "group-hover:text-white"
              }`}
            >
              {item.icon}
            </span>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
