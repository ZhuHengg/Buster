"use client";

import { useEffect, useState } from "react";

import { getCameras } from "@/lib/api";
import type { CameraConfig } from "@/lib/types";
import { useCmsSocket } from "@/lib/ws";

import CameraGrid, { CmsHeader } from "./CameraGrid";

export default function Dashboard() {
  const { state, connected } = useCmsSocket();
  const [cameras, setCameras] = useState<CameraConfig[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const load = () =>
      getCameras()
        .then((list) => !cancelled && setCameras(list))
        .catch(() => {
          if (!cancelled) timer = setTimeout(load, 2000); // backend may still be starting
        });
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  if (cameras === null) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <CmsHeader connected={connected} />
        <div className="flex flex-1 items-center justify-center text-sm text-muted">Connecting to cameras…</div>
      </div>
    );
  }
  return <CameraGrid cameras={cameras} state={state} connected={connected} />;
}
