"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, API_BASE, approve, reject } from "@/lib/api";
import { useCms } from "@/lib/cms";
import { OPERATOR_NAME, TOWNSHIP_NAME } from "@/lib/config";
import { summarizeStreams } from "@/lib/health";

import AlertCard from "./AlertCard";
import CameraGrid from "./CameraGrid";
import { PageHeader } from "./PageHeader";
import RecentEvents from "./RecentEvents";
import StatusStrip from "./StatusStrip";

const CLOSE_AFTER_MS = 5000;

function Toast({ text, onDone }: { text: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 4000);
    return () => clearTimeout(t);
  }, [text, onDone]);
  return (
    <div
      role="alert"
      className="fixed left-1/2 top-16 z-[60] -translate-x-1/2 rounded-[var(--r-md)] border border-warn bg-warn-tint px-4 py-2 text-sm font-semibold text-warn shadow-[var(--shadow-pop)]"
    >
      {text}
    </div>
  );
}

export default function Dashboard() {
  const { state, cameras, cameraLoadFailures, applyIncident, streams, reportStream } = useCms();
  const [busy, setBusy] = useState(false);
  const [focusId, setFocusId] = useState<string | null>(null); // incident kept open (approved one for its timeline, or one opened from the queue)
  const [toast, setToast] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false); // the operator closed the panel with ×; nothing else changes

  const pending = Object.values(state.incidents)
    .filter((i) => i.status === "PENDING_REVIEW")
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  const pendingCount = pending.length;
  // the panel shows the alert picked with Next / the events list, else the oldest pending one; × hides it
  const shownId = dismissed ? null : (focusId ?? pending[0]?.id ?? null);
  const shown = shownId ? state.incidents[shownId] : undefined;
  // Next and the "n of m" count walk every undecided alert
  const open = pending;
  const queueCount = shown?.status === "PENDING_REVIEW" ? Math.max(0, open.length - 1) : 0;
  const position =
    shown?.status === "PENDING_REVIEW" ? { index: open.findIndex((i) => i.id === shown.id) + 1, total: open.length } : undefined;
  const callStatus = focusId
    ? state.incidents[focusId]?.escalation.find((s) => s.channel === "police_call")?.status
    : undefined;
  const callFinished = callStatus === "completed" || callStatus === "failed";

  // a brand-new pending alert always brings the panel back
  const seenIds = useRef<Set<string>>(new Set());
  const pendingKey = pending.map((i) => i.id).join(",");
  useEffect(() => {
    const ids = pendingKey ? pendingKey.split(",") : [];
    if (ids.some((id) => !seenIds.current.has(id))) setDismissed(false);
    seenIds.current = new Set(ids);
  }, [pendingKey]);

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
        setToast(kind === "approve" ? `${updated.id} approved: escalation started` : `${updated.id} rejected as a false positive`);
        if (kind === "approve") setFocusId(updated.id);
        else setFocusId(null);
      } catch (err) {
        setToast(
          err instanceof ApiError && err.status === 409
            ? "Already handled by another operator"
            : "Action failed: the backend did not accept it. Please try again.",
        );
      } finally {
        setBusy(false);
      }
    },
    [shown, applyIncident],
  );

  // × only hides the panel. A pending alert stays pending and remembered, so reopening shows the same one.
  const closeAlert = useCallback(() => {
    setDismissed(true);
    if (focusId && state.incidents[focusId]?.status !== "PENDING_REVIEW") setFocusId(null);
  }, [focusId, state.incidents]);
  // skip to the next undecided alert (wraps around); the skipped one stays pending
  const nextAlert = useCallback(() => {
    if (!shown) return;
    const at = open.findIndex((i) => i.id === shown.id);
    const next = open[(at + 1) % open.length];
    if (next && next.id !== shown.id) setFocusId(next.id);
  }, [shown, open]);
  const reviewAlerts = useCallback(() => {
    setDismissed(false);
    setFocusId((f) => (f && state.incidents[f]?.status === "PENDING_REVIEW" ? f : null));
  }, [state.incidents]);
  const openIncident = useCallback((id: string) => {
    setDismissed(false);
    setFocusId(id);
  }, []);
  const clearToast = useCallback(() => setToast(null), []);

  if (cameras === null) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <PageHeader title="Live Monitoring" subtitle={TOWNSHIP_NAME} />
        {cameraLoadFailures >= 3 ? (
          <div role="alert" className="m-4 rounded-[var(--r-lg)] border border-warn bg-warn-tint p-4 text-sm">
            <p className="font-semibold text-warn">Cannot reach the monitoring backend at {API_BASE}</p>
            <p className="mt-1 text-ink">
              No camera list could be loaded, so no feeds are shown. Retrying every 2 seconds (attempt {cameraLoadFailures}).
            </p>
          </div>
        ) : (
          <div role="status" className="flex flex-1 items-center justify-center text-sm text-muted">
            Loading camera list…
          </div>
        )}
      </div>
    );
  }

  const summary = summarizeStreams(cameras, streams);
  const incidents = Object.values(state.incidents);
  return (
    <div className="relative flex min-h-0 flex-1">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <PageHeader
          title="Live Monitoring"
          subtitle={`${TOWNSHIP_NAME} · ${cameras.length} cameras · recorded demonstration clips, not live CCTV`}
        >
          <RecentEvents incidents={incidents} summary={summary} activeId={shownId} onOpen={openIncident} />
        </PageHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-2 p-3">
          <StatusStrip
            summary={summary}
            incidents={incidents}
            onReview={pendingCount > 0 ? reviewAlerts : undefined}
          />
          {cameras.length === 0 ? (
            <div className="flex flex-1 items-center justify-center rounded-[var(--r-lg)] border border-dashed border-line-strong text-sm text-muted">
              No cameras are configured.
            </div>
          ) : (
            <CameraGrid cameras={cameras} state={state} alertCameraId={shown?.status === "PENDING_REVIEW" ? shown.camera_id : undefined} streams={streams} onStream={reportStream} />
          )}
        </div>
      </div>
      {shown && (
        // beside the grid on wide screens; over it on narrower ones so the video keeps its width
        <div className="max-xl:absolute max-xl:inset-y-0 max-xl:right-0 max-xl:z-20 max-xl:shadow-[var(--shadow-pop)] xl:contents">
        <AlertCard
          incident={shown}
          camera={cameras.find((c) => c.id === shown.camera_id)}
          onApprove={() => void decide("approve")}
          onReject={() => void decide("reject")}
          onNext={nextAlert}
          position={position}
          onClose={closeAlert}
          busy={busy}
          queueCount={queueCount}
        />
        </div>
      )}
      {toast && <Toast text={toast} onDone={clearToast} />}
    </div>
  );
}
