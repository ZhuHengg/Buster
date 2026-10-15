// One stroke-icon family (24px grid, 1.8 stroke) used across the whole application.
const PATHS = {
  live: (
    <>
      <rect x="3" y="3" width="7.5" height="7.5" rx="1" />
      <rect x="13.5" y="3" width="7.5" height="7.5" rx="1" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="1" />
      <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1" />
    </>
  ),
  trace: (
    <>
      <path d="M12 21s-7-5.6-7-11a7 7 0 0 1 14 0c0 5.4-7 11-7 11z" />
      <circle cx="12" cy="10" r="2.6" />
    </>
  ),
  incidents: (
    <>
      <path d="M12 3.5 2.8 19.5a1 1 0 0 0 .9 1.5h16.6a1 1 0 0 0 .9-1.5z" />
      <path d="M12 10v4.5M12 17.6v.01" />
    </>
  ),
  analytics: <path d="M4 20V10M10 20V4M16 20v-7M21 20H3" />,
  camera: (
    <>
      <path d="M23 7l-7 5 7 5V7z" />
      <rect x="1" y="5" width="15" height="14" rx="2" />
    </>
  ),
  bell: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </>
  ),
  shield: (
    <>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  alert: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <path d="M12 7.5v5.5M12 16.4v.01" />
    </>
  ),
  nosignal: (
    <>
      <path d="M2 2l20 20" />
      <path d="M8.5 16.4a5 5 0 0 1 7 0M5 12.9a10 10 0 0 1 4-2.4M19 12.9a10 10 0 0 0-5.2-2.8M2 9.4a15 15 0 0 1 4.6-2.8M22 9.4a15 15 0 0 0-8-3.8" />
      <path d="M12 20v.01" />
    </>
  ),
  offline: (
    <>
      <path d="M12 3v8" />
      <path d="M6.4 6.6a8 8 0 1 0 11.2 0" />
    </>
  ),
  stale: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <path d="M12 7v5l3.2 2" />
    </>
  ),
  spinner: <path d="M12 3a9 9 0 1 0 9 9" />,
  retry: (
    <>
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 3v5h5" />
    </>
  ),
  expand: <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />,
  collapse: <path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />,
  pause: (
    <>
      <rect x="6.5" y="4.5" width="3.8" height="15" rx="0.8" />
      <rect x="13.7" y="4.5" width="3.8" height="15" rx="0.8" />
    </>
  ),
  play: <path d="M7 4.5v15l13-7.5z" />,
  chevronLeft: <path d="M15 5l-7 7 7 7" />,
  chevronRight: <path d="M9 5l7 7-7 7" />,
  chevronDown: <path d="M5 9l7 7 7-7" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  building: (
    <>
      <path d="M4 21V5l8-2v18M12 9h8v12M4 21h16" />
      <path d="M8 8v.01M8 12v.01M8 16v.01M16 13v.01M16 17v.01" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="3.6" />
      <path d="M4.5 20.5c.6-4 3.6-6 7.5-6s6.9 2 7.5 6" />
    </>
  ),
  grid: <path d="M3 3h18v18H3zM3 12h18M12 3v18" />,
  focus: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="1" />
      <path d="M15 3v18" />
    </>
  ),
  target: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.2" />
    </>
  ),
  filter: <path d="M3 5h18l-7 8.2V19l-4-2v-3.8z" />,
  cpu: (
    <>
      <rect x="6" y="6" width="12" height="12" rx="1.5" />
      <path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" />
    </>
  ),
} as const;

export type IconName = keyof typeof PATHS;

export default function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {PATHS[name]}
    </svg>
  );
}
