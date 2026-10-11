"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { getCameras } from "@/lib/api";
import type { CameraConfig } from "@/lib/types";
import { useCmsSocket } from "@/lib/ws";

import { CmsHeader } from "./CameraGrid";
import IncidentDetail from "./IncidentDetail";
import IncidentTable from "./IncidentTable";

export default function IncidentLog() {
  const { state, connected } = useCmsSocket();
  const [cameras, setCameras] = useState<CameraConfig[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    getCameras().then(setCameras).catch(() => undefined);
  }, []);

  const incidents = useMemo(() => Object.values(state.incidents), [state.incidents]);
  const selected = selectedId ? state.incidents[selectedId] : undefined;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <CmsHeader connected={connected}>
        <Link href="/" className="text-slate-200 underline-offset-4 hover:underline">
          Live monitoring
        </Link>
      </CmsHeader>
      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_420px]">
        <section className="flex min-h-0 flex-col gap-3">
          <h1 className="text-lg font-semibold text-slate-100">Incident log</h1>
          <IncidentTable incidents={incidents} selectedId={selectedId} onSelect={(i) => setSelectedId(i.id)} />
        </section>
        <aside className="min-h-0 overflow-y-auto rounded-md border border-line bg-panel p-4">
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
