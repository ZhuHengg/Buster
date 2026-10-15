"use client";

import { useEffect, useState } from "react";

const DURATION_MS = 800;

// Only called while rendering on the client (these values come from fetched data, never server-rendered).
const canAnimate = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Counts a formatted value such as "9.0 s", "92%" or "4" up from zero when it first appears.
 * Anything that does not start with a number (e.g. "—") is shown as is. No animation under
 * reduced motion, or where the browser cannot tell (tests), so the final value is always rendered.
 */
export default function CountUp({ value }: { value: string }) {
  const match = /^(-?\d+(?:\.\d+)?)([\s\S]*)$/.exec(value);
  const target = match ? Number(match[1]) : null;
  const decimals = match?.[1].split(".")[1]?.length ?? 0;
  const suffix = match?.[2] ?? "";
  const [progress, setProgress] = useState(() => (target !== null && canAnimate() ? 0 : 1));

  useEffect(() => {
    if (target === null || progress >= 1) return;
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION_MS);
      setProgress(1 - Math.pow(1 - t, 3));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // runs once per mount: the animation is the entrance, later value changes just show the new number
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (target === null || progress >= 1) return <>{value}</>;
  return (
    <>
      {(target * progress).toFixed(decimals)}
      {suffix}
    </>
  );
}
