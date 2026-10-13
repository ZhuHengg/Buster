"use client";

import { useState } from "react";

import { restartPlayback, setLoop } from "@/lib/api";
import type { PlaybackState } from "@/lib/types";

const BUTTON =
  "rounded border border-line bg-panel2 px-2 py-0.5 text-[11px] font-medium text-slate-200 hover:border-slate-400 disabled:opacity-50";

/** Stop the demo clips from looping so one pass can be inspected, and play it again on demand. */
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

  const status = playback.loop ? "Looping" : playback.held ? "Finished, holding on the last frame" : "Playing once";
  return (
    <div className="flex items-center gap-2" data-testid="playback-controls">
      <span className="text-[11px] text-muted">{status}</span>
      <button type="button" className={BUTTON} disabled={busy} onClick={() => void run(() => setLoop(!playback.loop))}>
        {playback.loop ? "Stop loop" : "Loop clips"}
      </button>
      <button type="button" className={BUTTON} disabled={busy} onClick={() => void run(restartPlayback)}>
        Restart
      </button>
      {error && (
        <span role="status" className="text-[11px] text-warn">
          Could not change playback
        </span>
      )}
    </div>
  );
}
