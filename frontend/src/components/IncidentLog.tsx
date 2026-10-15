"use client";

import { useEffect, useMemo, useState } from "react";

import { ApiError, deleteIncident, getCameras } from "@/lib/api";
import type { CameraConfig, Incident } from "@/lib/types";
import { useCmsSocket } from "@/lib/ws";

import { CmsHeader } from "./CameraGrid";
import IncidentDetail from "./IncidentDetail";
import IncidentTable from "./IncidentTable";

export default function IncidentLog() {
  const { state, connected, removeIncident } = useCmsSocket();
  const [cameras, setCameras] = useState<CameraConfig[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState(false);

  useEffect(() => {
    getCameras().then(setCameras).catch(() => undefined);
  }, []);

  const incidents = useMemo(() => Object.values(state.incidents), [state.incidents]);
  const selected = selectedId ? state.incidents[selectedId] : undefined;

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
      <CmsHeader
        connected={connected}
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
        <aside className="min-h-0 overflow-y-auto rounded-xl border border-line bg-panel p-4">
          {selected ? (
            <IncidentDetail incident={selected} camera={cameras.find((c) => c.id === selected.camera_id)} />
          ) : (
            <p className="py-10 text-center text-sm text-muted">Select an incident to see its clip, evidence and escalation.</p>
          )}
        </aside>
      </main>
    </div>
  );
}
