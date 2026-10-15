"use client";

import { useState } from "react";

import { restartPlayback, setPaused } from "@/lib/api";
import type { PlaybackState } from "@/lib/types";

const ICON = { fill: "currentColor", "aria-hidden": true } as const;

/** Freeze every camera on its current frame so the operator can look closely, then carry on. */
export default function PlaybackControls({ playback }: { playback: PlaybackState }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(false);
    try {
      await action();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2" data-testid="playback-controls">
      {error && (
        <span role="status" className="text-[11px] text-warn">
          Could not change playback
        </span>
      )}
      <div className="flex items-center rounded-full border border-line bg-panel p-0.5">
        <button
          type="button"
          disabled={busy}
          onClick={() => void run(() => setPaused(!playback.paused))}
          aria-pressed={playback.paused}
          title={playback.paused ? "Resume all camera feeds" : "Freeze all camera feeds on the current frame"}
          className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition disabled:opacity-50 ${
            playback.paused ? "bg-warn text-slate-900" : "text-slate-100 hover:bg-white/10"
          }`}
        >
          {playback.paused ? (
            <svg viewBox="0 0 24 24" width="13" height="13" {...ICON}>
              <path d="M7 4.5v15l13-7.5z" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" width="13" height="13" {...ICON}>
              <rect x="6" y="4.5" width="4.2" height="15" rx="1" />
              <rect x="13.8" y="4.5" width="4.2" height="15" rx="1" />
            </svg>
          )}
          {playback.paused ? "Resume" : "Pause"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void run(restartPlayback)}
          title="Replay the clips from the start"
          className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium text-slate-300 transition hover:bg-white/10 hover:text-white disabled:opacity-50"
        >
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
            <path d="M3 3v5h5" />
          </svg>
          Restart
        </button>
      </div>
    </div>
  );
}
