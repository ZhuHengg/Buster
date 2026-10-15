"use client";

import { useState } from "react";

import { restartPlayback, setPaused } from "@/lib/api";
import type { PlaybackState } from "@/lib/types";

import Icon from "./Icon";

/** Scope is stated on the buttons themselves: both act on EVERY camera, not the selected one. */
export default function PlaybackControls({ playback, cameraCount }: { playback: PlaybackState; cameraCount?: number }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [confirmRestart, setConfirmRestart] = useState(false);

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

  const all = cameraCount ? `all ${cameraCount} cameras` : "all cameras";
  const btn =
    "flex items-center gap-1.5 rounded-[var(--r-md)] border px-2.5 py-1.5 text-xs font-semibold transition disabled:opacity-50";

  return (
    <div className="relative flex items-center gap-2" data-testid="playback-controls">
      {error && (
        <span role="status" className="text-xs font-medium text-crit">
          Could not change playback. Is the backend running?
        </span>
      )}
      <button
        type="button"
        disabled={busy}
        onClick={() => void run(() => setPaused(!playback.paused))}
        aria-pressed={playback.paused}
        title={
          playback.paused
            ? `Resume playback on ${all}`
            : `Freeze ${all} on the current frame. Detection and alerts continue; the picture simply stops.`
        }
        className={`${btn} ${
          playback.paused
            ? "border-warn bg-warn-tint text-warn"
            : "border-line-strong bg-panel text-ink hover:bg-panel2"
        }`}
      >
        <Icon name={playback.paused ? "play" : "pause"} size={14} />
        {playback.paused ? "Resume all feeds" : "Pause all feeds"}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => setConfirmRestart(true)}
        aria-expanded={confirmRestart}
        title={`Replay the clips on ${all} from the start`}
        className={`${btn} border-line-strong bg-panel text-ink hover:bg-panel2`}
      >
        <Icon name="retry" size={14} />
        Restart all clips
      </button>
      {confirmRestart && (
        <div
          role="alertdialog"
          aria-label="Confirm restart"
          className="absolute right-0 top-full z-30 mt-2 w-72 rounded-[var(--r-lg)] border border-line-strong bg-panel p-3 text-left shadow-[var(--shadow-pop)]"
        >
          <p className="text-sm font-semibold text-ink">Restart {all} from the beginning?</p>
          <p className="mt-1 text-xs text-muted">
            Every clip replays from 00:00 and live tracking boxes start again. Incidents already raised are kept.
          </p>
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              autoFocus
              onClick={() => setConfirmRestart(false)}
              className="rounded-[var(--r-md)] border border-line-strong px-3 py-1.5 text-xs font-semibold text-ink hover:bg-panel2"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setConfirmRestart(false);
                void run(restartPlayback);
              }}
              className="rounded-[var(--r-md)] bg-brand px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-strong"
            >
              Restart clips
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
