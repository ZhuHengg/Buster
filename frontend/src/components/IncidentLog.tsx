"use client";

import { useEffect, useMemo, useState } from "react";

import { ApiError, approve, deleteIncident, getCameras, reject } from "@/lib/api";
import { OPERATOR_NAME } from "@/lib/config";
import type { CameraConfig, Incident } from "@/lib/types";
import { useCms } from "@/lib/cms";

import { PageHeader } from "./PageHeader";
import IncidentDetail from "./IncidentDetail";
import IncidentTable from "./IncidentTable";

export default function IncidentLog() {
  const { state, removeIncident, applyIncident } = useCms();
  const [cameras, setCameras] = useState<CameraConfig[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    getCameras().then(setCameras).catch(() => undefined);
  }, []);

  const incidents = useMemo(() => Object.values(state.incidents), [state.incidents]);
  const selected = selectedId ? state.incidents[selectedId] : undefined;
  // undecided incidents in the same order as the table (newest first); Next walks them and wraps around
  const pending = useMemo(
    () =>
      incidents
        .filter((i) => i.status === "PENDING_REVIEW")
        .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)),
    [incidents],
  );
  const at = selected ? pending.findIndex((i) => i.id === selected.id) : -1;
  const nextPending = () => {
    if (pending.length === 0) return;
    setNotice(null);
    setSelectedId(pending[(at + 1) % pending.length].id);
  };
  const decide = async (kind: "approve" | "reject") => {
    if (!selected || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      applyIncident(await (kind === "approve" ? approve : reject)(selected.id, OPERATOR_NAME));
      setNotice(kind === "approve" ? "Approved: escalation started" : "Rejected as a false positive");
    } catch (err) {
      setNotice(
        err instanceof ApiError && err.status === 409
          ? "Already handled by another operator"
          : "Action failed: the backend did not accept it. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  const remove = async (incident: Incident) => {
    setRemoveError(false);
    try {
      await deleteIncident(incident.id);
    } catch (err) {
      // already gone on the server (another tab removed it): just drop it here too
      if (!(err instanceof ApiError && err.status === 404)) {
        setRemoveError(true);
        return;
      }
    }
    removeIncident(incident.id);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader
        title="Incident log"
        subtitle={`${incidents.length} ${incidents.length === 1 ? "incident" : "incidents"} · select one to see its clip, evidence and escalation`}
      />
      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_420px]">
        <section className="flex min-h-0 flex-col gap-3">
          {removeError && (
            <p role="status" className="text-sm text-warn">
              Could not remove the incident. Is the backend running?
            </p>
          )}
          <IncidentTable
            incidents={incidents}
            selectedId={selectedId}
            onSelect={(i) => setSelectedId(i.id)}
            onRemove={(i) => void remove(i)}
          />
        </section>
        <aside className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-panel">
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {selected ? (
              <IncidentDetail incident={selected} camera={cameras.find((c) => c.id === selected.camera_id)} />
            ) : (
              <p className="py-10 text-center text-sm text-muted">Select an incident to see its clip, evidence and escalation.</p>
            )}
          </div>
          {(selected?.status === "PENDING_REVIEW" || pending.length > 0 || notice) && (
            <div className="flex shrink-0 flex-col gap-2 border-t border-line px-4 py-3">
              {notice && (
                <p role="status" className="text-center text-xs text-muted">
                  {notice}
                </p>
              )}
              {selected?.status === "PENDING_REVIEW" && (
                <>
                  <button
                    type="button"
                    onClick={() => void decide("approve")}
                    disabled={busy}
                    className="cursor-pointer rounded-full bg-accent px-4 py-3 text-sm font-semibold uppercase tracking-wide text-white transition hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Approve &amp; escalate
                  </button>
                  <button
                    type="button"
                    onClick={() => void decide("reject")}
                    disabled={busy}
                    className="cursor-pointer rounded-full border border-line-strong px-4 py-2.5 text-sm font-medium text-ink transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Reject (false positive)
                  </button>
                </>
              )}
              {pending.length > (selected?.status === "PENDING_REVIEW" ? 1 : 0) && (
                <button
                  type="button"
                  onClick={nextPending}
                  disabled={busy}
                  className="flex cursor-pointer items-center justify-center gap-2 rounded-full border border-line px-4 py-2.5 text-sm font-medium text-ink transition hover:border-line-strong hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {at >= 0 ? "Next pending" : "Review next pending"}
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d="M9 5l7 7-7 7" />
                  </svg>
                  <span className="mono-time rounded-full bg-white/10 px-2 py-0.5 text-xs leading-none text-muted">
                    {at >= 0 ? `${at + 1} / ${pending.length}` : pending.length}
                  </span>
                </button>
              )}
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}
