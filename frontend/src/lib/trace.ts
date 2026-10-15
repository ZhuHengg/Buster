// SPIKE (throwaway): mock data for the suspect trace map. No backend, no real cross-camera tracking.
// Coordinates are real (City of Elmina, Shah Alam) and the route was pre-computed once from
// OpenStreetMap roads (OSRM) so it follows real streets. Camera positions are invented.

export type LatLng = [number, number];

export const MAP_CENTER: LatLng = [3.2028, 101.4998];
export const MAP_ZOOM = 15;

export interface MapCamera {
  id: string;
  label: string;
  at: LatLng;
}

export interface Sighting {
  cameraId: string;
  label: string;
  at: LatLng;
  offsetS: number; // seconds after the snatch
  match: number; // 0..1 re-identification confidence
  note: string;
}

export const MAP_CAMERAS: MapCamera[] = [
  { id: "CAM-01", label: "Row A", at: [3.20157, 101.50059] },
  { id: "CAM-02", label: "Row B front", at: [3.20101, 101.50069] },
  { id: "CAM-03", label: "Bus Stop Jalan Elmina 2", at: [3.20399, 101.50072] },
  { id: "CAM-05", label: "Pasar Mini Car Park", at: [3.20032, 101.50176] },
  { id: "CAM-06", label: "Community Hall", at: [3.19742, 101.50186] },
  { id: "CAM-07", label: "Row B rear lane", at: [3.19987, 101.50093] },
];

// Each sighting sits on the escape route (the segments below join them end to end).
export const SIGHTINGS: Sighting[] = [
  { cameraId: "CAM-07", label: "Row B rear lane", at: [3.19987, 101.50093], offsetS: 0, match: 0.97, note: "Snatch. Suspect on motorcycle." },
  { cameraId: "CAM-05", label: "Pasar Mini Car Park", at: [3.20032, 101.50176], offsetS: 40, match: 0.94, note: "Riding north, same motorcycle." },
  { cameraId: "CAM-03", label: "Bus Stop Jalan Elmina 2", at: [3.20399, 101.50072], offsetS: 85, match: 0.91, note: "Heading for the north gate on Persiaran Casuarina." },
];

// Segment i runs from sighting i-1 to sighting i (segment 0 is empty: the suspect starts at CAM-07).
export const SEGMENTS: LatLng[][] = [
  [],
  [[3.19987, 101.50093], [3.19975, 101.50027], [3.19919, 101.50038], [3.19896, 101.50042], [3.19913, 101.50158], [3.19916, 101.50171], [3.19923, 101.50186], [3.19927, 101.50190], [3.19935, 101.50193], [3.19940, 101.50194], [3.20032, 101.50176]],
  [[3.20032, 101.50176], [3.20221, 101.50139], [3.20223, 101.50139], [3.20233, 101.50136], [3.20298, 101.50122], [3.20332, 101.50113], [3.20362, 101.50099], [3.20384, 101.50085], [3.20399, 101.50072]],
];

// Where the suspect is heading after the last camera that saw them: dotted on the map.
export const PREDICTED: LatLng[] = [[3.20399, 101.50072], [3.20409, 101.50062], [3.20429, 101.50037], [3.20444, 101.50010], [3.20448, 101.50000], [3.20455, 101.50002], [3.20497, 101.50017], [3.20577, 101.50050], [3.20601, 101.50059], [3.20613, 101.50065], [3.20633, 101.50078], [3.20653, 101.50032], [3.20653, 101.50032], [3.20658, 101.50021], [3.20699, 101.49921], [3.20734, 101.49815], [3.20737, 101.49800], [3.20736, 101.49788], [3.20736, 101.49770], [3.20732, 101.49765], [3.20730, 101.49760], [3.20729, 101.49753], [3.20731, 101.49745], [3.20734, 101.49738], [3.20739, 101.49733], [3.20743, 101.49730], [3.20747, 101.49729], [3.20755, 101.49700], [3.20762, 101.49676], [3.20764, 101.49646], [3.20767, 101.49617], [3.20771, 101.49586], [3.20774, 101.49558], [3.20777, 101.49341], [3.20775, 101.49282], [3.20775, 101.49282]];

/** Simulated seconds per real second in the demo replay. */
export const SPEEDUP = 15;

export const revealDelayMs = (s: Sighting) => Math.round((s.offsetS / SPEEDUP) * 1000);
