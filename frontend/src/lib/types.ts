// TypeScript mirrors of the backend models (snake_case kept to match the JSON exactly).

export type Direction = "left" | "right" | "up" | "down";

export type IncidentStatus =
  | "CANDIDATE"
  | "AI_REJECTED"
  | "PENDING_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "ESCALATED";

export interface Track {
  id: number;
  cls: "person" | "motorcycle";
  bbox: [number, number, number, number]; // x1, y1, x2, y2 in source pixels
  suspect: boolean;
}

export interface DetectionsMsg {
  type: "detections";
  camera_id: string;
  loop: number;
  pts: number;
  frame_w: number;
  frame_h: number;
  tracks: Track[];
}

export interface SyncMsg {
  type: "camera.sync";
  camera_id: string;
  loop: number;
  pts: number;
  wall_time: number; // unix seconds when pts was measured
}

export interface PersonDesc {
  track_id: number | null;
  description: string;
}

export interface VehicleDesc {
  type: string;
  colour: string;
  plate_visible: boolean;
  plate_text: string | null;
}

export interface VerificationResult {
  is_incident: boolean;
  incident_type: "snatch_theft" | "robbery" | "assault" | "other" | "none";
  confidence: number; // 0..1
  summary: string;
  suspects: PersonDesc[];
  victim: PersonDesc | null;
  vehicle: VehicleDesc | null;
  escape_direction: "north" | "south" | "east" | "west" | "unknown";
}

export interface EscalationStep {
  channel: "police_call" | "police_sms" | "gate_sms";
  status: "queued" | "ringing" | "in_progress" | "completed" | "sent" | "failed" | "skipped";
  detail: string | null;
  updated_at: string;
}

export interface CandidateEvent {
  camera_id: string;
  pts: number;
  loop: number;
  trigger: "rule" | "model";
  suspect_track_ids: number[];
  victim_track_id: number | null;
  motorcycle_track_id: number | null;
  detected_at: string;
}

export interface Incident {
  id: string;
  camera_id: string;
  status: IncidentStatus;
  candidate: CandidateEvent;
  verification: VerificationResult | null;
  verification_error: string | null;
  escape_direction: string | null; // compass word
  escape_exit: string | null;
  snapshot_files: string[];
  clip_file: string;
  clip_start: number;
  clip_end: number;
  guard_decision_at: string | null;
  operator: string | null;
  escalation: EscalationStep[];
  metrics: Record<string, number>; // candidate_s, verified_s, shown_s, call_placed_s
  created_at: string;
}

export interface CameraSyncInfo {
  fps: number;
  duration: number;
  width: number;
  height: number;
}

export interface CameraConfig {
  id: string;
  name: string;
  location: string;
  clip: string | null;
  analyse: boolean;
  exits: Partial<Record<Direction, string>>;
  compass: Partial<Record<Direction, string>>;
  sync: CameraSyncInfo | null;
}

export interface IncidentUpdatedMsg {
  type: "incident.updated";
  incident: Incident;
}

export type WsMsg = DetectionsMsg | SyncMsg | IncidentUpdatedMsg;
