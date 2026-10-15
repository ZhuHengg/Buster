"use client";

// SPIKE (throwaway): mock live trace of the suspect across cameras on an OpenStreetMap base (Leaflet).

import "leaflet/dist/leaflet.css";

import type * as Leaflet from "leaflet";
import { useEffect, useMemo, useRef, useState } from "react";

import { snapshotUrl } from "@/lib/api";
import {
  MAP_CAMERAS,
  MAP_CENTER,
  MAP_ZOOM,
  PREDICTED,
  SEGMENTS,
  SIGHTINGS,
  revealDelayMs,
} from "@/lib/trace";
import type { Incident } from "@/lib/types";
import { useCmsSocket } from "@/lib/ws";

import { CmsHeader } from "./CameraGrid";

const clock = (base: number, offsetS: number) =>
  new Date(base + offsetS * 1000).toLocaleTimeString("en-GB", { hour12: false });

const CAM_SVG =
  '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="2" y="7" width="13" height="10" rx="2"/><path d="M16 11l6-3.5v9L16 13z"/></svg>';
const SILHOUETTE =
  '<div style="display:flex;height:96px;align-items:center;justify-content:center;border-radius:4px;background:#141b24;color:#8b98a9"><svg viewBox="0 0 24 24" width="44" height="44" fill="currentColor"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7z"/></svg></div>';

function Suspect({ src, className }: { src: string | null; className: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className={`${className} flex items-center justify-center bg-panel2 text-muted`} aria-label="Suspect photo">
        <svg viewBox="0 0 24 24" className="h-1/2 w-1/2" fill="currentColor" aria-hidden>
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7z" />
        </svg>
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt="Suspect" onError={() => setFailed(true)} className={`${className} bg-black object-contain`} />;
}

export default function TraceMap() {
  const { state, connected } = useCmsSocket();
  const [revealed, setRevealed] = useState(0); // how many sightings are on the map
  const [run, setRun] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [lastRevealAt, setLastRevealAt] = useState(() => Date.now());
  const [ready, setReady] = useState(false);

  const mapEl = useRef<HTMLDivElement>(null);
  const lib = useRef<typeof Leaflet | null>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const pins = useRef(new Map<string, Leaflet.Marker>());
  const drawn = useRef<Leaflet.Polyline[]>([]);
  const predicted = useRef<Leaflet.Polyline | null>(null);
  const popup = useRef<Leaflet.Popup | null>(null);

  // the snatch on CAM-07, if the live system has one; otherwise a pure mock anchored to "now"
  const incident: Incident | undefined = useMemo(() => {
    const list = Object.values(state.incidents).filter((i) => i.camera_id === "CAM-07");
    list.sort((a, b) => Date.parse(b.candidate.detected_at) - Date.parse(a.candidate.detected_at));
    return list.find((i) => i.status === "ESCALATED") ?? list[0];
  }, [state.incidents]);
  const [fallbackBase] = useState(() => Date.now());
  const base = incident ? Date.parse(incident.candidate.detected_at) : fallbackBase;
  const photo = incident?.snapshot_files[0] ? snapshotUrl(incident.snapshot_files[0]) : null;

  const lastIdx = Math.max(0, revealed - 1);
  const shownIdx = picked !== null && picked < revealed ? picked : lastIdx;
  const shown = SIGHTINGS[shownIdx];
  const last = SIGHTINGS[lastIdx];
  const done = revealed === SIGHTINGS.length;
  const lastSeenAgo = Math.max(0, Math.floor((now - lastRevealAt) / 1000));

  // build the map once
  useEffect(() => {
    let cancelled = false;
    const pinsMap = pins.current;
    void import("leaflet").then((L) => {
      if (cancelled || !mapEl.current) return;
      lib.current = L;
      const m = L.map(mapEl.current, { center: MAP_CENTER, zoom: MAP_ZOOM, zoomControl: true });
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(m);
      for (const c of MAP_CAMERAS) {
        const pin = L.marker(c.at, {
          icon: L.divIcon({ className: "cam-icon", html: `<div class="cam-pin">${CAM_SVG}</div>`, iconSize: [30, 30], iconAnchor: [15, 15] }),
          title: `${c.id} ${c.label}`,
          keyboard: false,
        }).addTo(m);
        pin.on("click", () => {
          const si = SIGHTINGS.findIndex((s) => s.cameraId === c.id);
          if (si >= 0) setPicked(si);
        });
        pinsMap.set(c.id, pin);
      }
      // route lines are created up front (adding vector layers mid-flyTo mis-projects them) and only shown later
      drawn.current = SEGMENTS.map((seg) => {
        const line = L.polyline(seg, { color: "#dc2626", weight: 5, opacity: 0.9, lineCap: "round", lineJoin: "round", className: "trace-line" }).addTo(m);
        line.getElement()?.setAttribute("pathLength", "1");
        return line;
      });
      predicted.current = L.polyline(PREDICTED, { color: "#dc2626", weight: 4, dashArray: "2 10", lineCap: "round", className: "trace-pred" }).addTo(m);
      map.current = m;
      setReady(true);
    });
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
      pinsMap.clear();
      drawn.current = [];
      predicted.current = null;
      popup.current = null;
      setReady(false);
    };
  }, []);

  // reveal sightings on a timer
  useEffect(() => {
    const timers = SIGHTINGS.map((s, i) =>
      setTimeout(() => {
        setRevealed(i + 1);
        setLastRevealAt(Date.now());
      }, revealDelayMs(s) + 1200),
    );
    return () => timers.forEach(clearTimeout);
  }, [run]);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // keep the map in step with what has been revealed / selected
  useEffect(() => {
    const L = lib.current;
    const m = map.current;
    if (!ready || !L || !m) return;

    // route segments draw in as each sighting is reached
    drawn.current.forEach((line, i) => line.getElement()?.classList.toggle("on", i > 0 && i <= revealed - 1));
    predicted.current?.getElement()?.classList.toggle("on", done);

    // camera pins: seen = amber, newest = red + pulse, selected = ringed
    for (const c of MAP_CAMERAS) {
      const si = SIGHTINGS.findIndex((s) => s.cameraId === c.id);
      const lit = si >= 0 && si < revealed;
      const cls = ["cam-pin", lit ? "lit" : "", lit && si === lastIdx ? "last" : "", lit && si === shownIdx ? "sel" : ""].join(" ");
      pins.current.get(c.id)?.setIcon(
        L.divIcon({
          className: "cam-icon",
          html: `<div class="${cls}">${CAM_SVG}${lit ? `<span class="cam-tag">${c.id}</span>` : ""}</div>`,
          iconSize: [30, 30],
          iconAnchor: [15, 15],
        }),
      );
      pins.current.get(c.id)?.setZIndexOffset(lit ? (si === lastIdx ? 1000 : 500) : 0);
    }

    // photo callout on the selected sighting
    if (revealed > 0) {
      const img = photo ? `<img src="${photo}" alt="Suspect" style="height:96px;width:100%;border-radius:4px;background:#000;object-fit:contain"/>` : SILHOUETTE;
      const html = `${img}<div style="margin-top:4px;font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#ef4444">${shownIdx === lastIdx ? "Last seen" : "Seen"}</div><div style="font-size:12px">${shown.label}</div><div style="font-family:ui-monospace,Consolas,monospace;font-size:11px;color:#8b98a9">${clock(base, shown.offsetS)}</div>`;
      if (!popup.current) {
        popup.current = L.popup({ closeButton: false, autoClose: false, closeOnClick: false, className: "trace-popup", offset: [0, -14] });
      }
      popup.current.setLatLng(shown.at).setContent(html);
      if (!popup.current.isOpen()) popup.current.openOn(m);
    } else {
      popup.current?.remove();
    }

    // follow the suspect, then frame the whole trace once located
    if (revealed > 0 && !done) m.flyTo(last.at, 16, { duration: 1.2 });
    if (done && picked === null) {
      const bounds = L.latLngBounds([...SEGMENTS.flat(), ...PREDICTED]);
      m.flyToBounds(bounds, { padding: [60, 60], duration: 1.4, maxZoom: 16 });
    } else if (picked !== null) {
      m.panTo(shown.at);
    }
  }, [ready, revealed, shownIdx, picked, done, lastIdx, last, shown, photo, base]);

  const replay = () => {
    setRevealed(0);
    setPicked(null);
    setRun((n) => n + 1);
    map.current?.flyTo(MAP_CENTER, MAP_ZOOM, { duration: 1 });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <CmsHeader
        connected={connected}
        title="Live trace"
        subtitle={done ? "Suspect located · police have been given the last known position" : "Following the suspect across nearby cameras"}
      />

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-[minmax(0,1fr)_380px]">
        <section className="relative min-h-[360px] overflow-hidden rounded-xl border border-line bg-panel">
          <div ref={mapEl} className="absolute inset-0" />
          <div className="pointer-events-none absolute left-14 top-3 z-[1000] rounded border border-warn/70 bg-black/75 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-warn">
            Demo · simulated cross-camera feed
          </div>
        </section>

        <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto rounded-xl border border-line bg-panel p-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">
              {done ? "Suspect located" : "Tracing suspect"}
            </div>
            <div className="text-lg font-semibold text-slate-50">Snatch theft · {incident?.id ?? "CAM-07 demo"}</div>
            <div className="text-xs text-muted">Police notified · units heading to {last.label}</div>
          </div>

          <div className="flex gap-3 rounded-xl border border-line bg-panel2 p-3">
            <Suspect src={photo} className="h-28 w-24 shrink-0 rounded-xl border border-line" />
            <dl className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
              <dt className="text-xs uppercase tracking-wide text-muted">{shownIdx === lastIdx ? "Last seen" : "Seen at"}</dt>
              <dd className="font-medium text-slate-50">
                {revealed > 0 ? `${shown.cameraId} · ${shown.label}` : "Locating…"}
              </dd>
              {revealed > 0 && (
                <>
                  <dd className="mono-time text-xs text-muted">
                    {clock(base, shown.offsetS)}
                    {shownIdx === lastIdx && ` · ${lastSeenAgo}s ago`}
                  </dd>
                  <dd className="text-xs text-slate-200">{shown.note}</dd>
                  <dd className="mono-time text-xs text-ok">Match {Math.round(shown.match * 100)}%</dd>
                </>
              )}
            </dl>
          </div>

          <ol className="flex flex-col">
            {SIGHTINGS.map((s, i) => {
              const on = i < revealed;
              return (
                <li key={s.cameraId}>
                  <button
                    type="button"
                    disabled={!on}
                    onClick={() => setPicked(i)}
                    className={`grid w-full grid-cols-[18px_1fr_auto] items-center gap-2 border-l-2 py-2 pl-2 text-left text-sm disabled:opacity-35 ${
                      i === shownIdx && on ? "border-accent bg-white/5" : "border-line"
                    }`}
                  >
                    <span className={`h-2.5 w-2.5 rounded-full ${on ? (i === lastIdx ? "bg-accent" : "bg-warn") : "bg-slate-600"}`} />
                    <span className="min-w-0 truncate text-slate-100">
                      {s.cameraId} · {s.label}
                    </span>
                    <span className="mono-time text-xs text-muted">{on ? `T+${s.offsetS}s` : "…"}</span>
                  </button>
                </li>
              );
            })}
          </ol>

          <button
            type="button"
            onClick={replay}
            className="mt-auto rounded-xl border border-slate-500 px-3 py-2 text-sm text-slate-200 transition hover:bg-white/5"
          >
            Replay trace
          </button>
        </aside>
      </main>
    </div>
  );
}
