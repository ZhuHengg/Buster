"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, API_BASE, approve, getCameras, reject } from "@/lib/api";
import { OPERATOR_NAME } from "@/lib/config";
import type { CameraConfig } from "@/lib/types";
import { useCmsSocket } from "@/lib/ws";

import AlertCard from "./AlertCard";
import CameraGrid, { CmsHeader } from "./CameraGrid";

const CLOSE_AFTER_MS = 5000;

function Toast({ text, onDone }: { text: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 4000);
    return () => clearTimeout(t);
  }, [text, onDone]);
  return (
    <div
      role="alert"
      className="fixed left-1/2 top-4 z-[60] -translate-x-1/2 rounded-xl border border-warn/70 bg-panel px-4 py-2 text-sm font-medium text-warn shadow-xl"
    >
      {text}
    </div>
  );
}

export default function Dashboard() {
  const { state, connected, applyIncident } = useCmsSocket();
  const [cameras, setCameras] = useState<CameraConfig[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [focusId, setFocusId] = useState<string | null>(null); // approved incident kept open for its timeline
  const [toast, setToast] = useState<string | null>(null);
  const [closedIds, setClosedIds] = useState<string[]>([]); // pending alerts the operator closed without deciding
  const [loadFailures, setLoadFailures] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const load = () =>
      getCameras()
        .then((list) => !cancelled && setCameras(list))
        .catch(() => {
          if (cancelled) return;
          setLoadFailures((n) => n + 1);
          timer = setTimeout(load, 2000); // backend may still be starting
        });
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  const pending = Object.values(state.incidents)
    .filter((i) => i.status === "PENDING_REVIEW")
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  const pendingCount = pending.length;
  // the oldest pending alert the operator has not closed; closed ones wait behind the "Review alerts" button
  const nextOpen = pending.find((i) => !closedIds.includes(i.id));
  const shownId = focusId ?? nextOpen?.id ?? null;
  const shown = shownId ? state.incidents[shownId] : undefined;
  const queueCount = shown?.status === "PENDING_REVIEW" ? pending.filter((i) => i.id !== shown.id && !closedIds.includes(i.id)).length : 0;
  const callStatus = focusId
    ? state.incidents[focusId]?.escalation.find((s) => s.channel === "police_call")?.status
    : undefined;
  const callFinished = callStatus === "completed" || callStatus === "failed";

  // the card stays open while the call is placed, then closes by itself
  useEffect(() => {
    if (!focusId || !callFinished) return;
    const t = setTimeout(() => setFocusId(null), CLOSE_AFTER_MS);
    return () => clearTimeout(t);
  }, [focusId, callFinished]);

  const decide = useCallback(
    async (kind: "approve" | "reject") => {
      if (!shown) return;
      setBusy(true);
      try {
        const updated = await (kind === "approve" ? approve : reject)(shown.id, OPERATOR_NAME);
        applyIncident(updated);
        if (kind === "approve") setFocusId(updated.id);
      } catch (err) {
        setToast(
          err instanceof ApiError && err.status === 409 ? "Already handled" : "Action failed. Please try again.",
        );
      } finally {
        setBusy(false);
      }
    },
    [shown, applyIncident],
  );

  const closeAlert = useCallback(() => {
    if (focusId) setFocusId(null);
    else if (shownId) setClosedIds((ids) => [...ids, shownId]);
  }, [focusId, shownId]);
  const reviewAlerts = useCallback(() => {
    setFocusId(null);
    setClosedIds([]);
  }, []);
  const clearToast = useCallback(() => setToast(null), []);

  if (cameras === null) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <CmsHeader connected={connected} title="Live monitoring" />
        {loadFailures >= 3 ? (
          <div role="status" className="flex flex-1 flex-col items-center justify-center gap-1 text-sm">
            <span className="font-medium text-warn">Can&apos;t reach the backend at {API_BASE}</span>
            <span className="text-xs text-muted">Is it running? Retrying every 2 s (attempt {loadFailures})</span>
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center text-sm text-muted">Connecting to cameras…</div>
        )}
      </div>
    );
  }
  return (
    <div className="flex min-h-0 flex-1">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <CameraGrid
          cameras={cameras}
          state={state}
          connected={connected}
          pendingCount={pendingCount}
          onReview={reviewAlerts}
        />
      </div>
      {shown && (
        <AlertCard
          incident={shown}
          camera={cameras.find((c) => c.id === shown.camera_id)}
          onApprove={() => void decide("approve")}
          onReject={() => void decide("reject")}
          onClose={closeAlert}
          busy={busy}
          queueCount={queueCount}
        />
      )}
      {toast && <Toast text={toast} onDone={clearToast} />}
    </div>
  );
}
