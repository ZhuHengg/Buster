import { BLADES, INNER, MARK_CX as CX, MARK_CY as CY, SHIELD, SWEEP, TICKS } from "./logoGeometry";

const DARK = "#18181a";
const ACCENT = "#ffc27a";

/**
 * Buster mark: an orange shield around a camera iris, drawn like a scanner HUD: tick-mark bezel,
 * concentric rings, aperture blades, a bright pupil and (when animated) a slow light-amber radar sweep.
 */
export function LogoMark({ size = 36, id = "buster", animated = false }: { size?: number; id?: string; animated?: boolean }) {
  return (
    <svg viewBox="0 0 48 56" width={(size * 48) / 56} height={size} aria-hidden="true" className="shrink-0">
      <defs>
        <linearGradient id={`${id}-shield`} x1="24" y1="2" x2="24" y2="54" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#ff8a1f" />
          <stop offset="0.6" stopColor="#f26a1d" />
          <stop offset="1" stopColor="#9a3412" />
        </linearGradient>
        <radialGradient id={`${id}-glow`} cx={CX} cy={CY} r="7" gradientUnits="userSpaceOnUse">
          <stop offset="0.55" stopColor={DARK} />
          <stop offset="0.7" stopColor="#7c2d12" />
          <stop offset="1" stopColor="#f26a1d" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`${id}-sweep`} x1={CX + 10.4} y1={CY} x2={CX + 5} y2={CY - 9} gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor={ACCENT} stopOpacity="0.75" />
          <stop offset="1" stopColor={ACCENT} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={SHIELD} fill={`url(#${id}-shield)`} />
      <path d={INNER} fill="none" stroke={DARK} strokeWidth="0.9" />
      {/* scanner bezel */}
      {TICKS.map(([x1, y1, x2, y2, major], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={DARK} strokeWidth={major ? 1.1 : 0.6} />
      ))}
      {[14, 12.2, 10.4].map((r) => (
        <circle key={r} cx={CX} cy={CY} r={r} fill="none" stroke={DARK} strokeWidth="1" />
      ))}
      {BLADES.map(([x1, y1, x2, y2], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={DARK} strokeWidth="0.9" strokeLinecap="round" />
      ))}
      <circle cx={CX} cy={CY} r="7" fill={`url(#${id}-glow)`} />
      <circle cx={CX} cy={CY} r="3.9" fill={DARK} />
      <path d={SWEEP} fill={`url(#${id}-sweep)`} className={animated ? "radar-sweep" : undefined} />
      <circle cx="26.3" cy="25.8" r="1.1" fill="#fff" />
      <circle cx={CX} cy={CY} r="3.9" fill="none" stroke={ACCENT} strokeWidth="0.5" strokeOpacity="0.9" />
    </svg>
  );
}

export default function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark size={40} animated />
      <span className="flex flex-col leading-none">
        <span className="bg-gradient-to-r from-white to-[#ffb27a] bg-clip-text text-[20px] font-black uppercase tracking-[0.2em] text-transparent">
          Buster
        </span>
        <span className="mt-1 flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.3em] text-[#ffc27a]">
          <span aria-hidden className="h-1 w-1 rounded-full bg-[#ffc27a]" />
          AI Surveillance
        </span>
      </span>
    </span>
  );
}
