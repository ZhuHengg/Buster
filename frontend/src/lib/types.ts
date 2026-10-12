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
  trigger: "rule" | "model" | "llm";
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

// ---- GET /api/reports -----------------------------------------------------------------------
export interface ReportMeta {
  commit: string;
  generated_at: string;
  triggers: string;
  verifier: string; // "mock" marks a benchmark as not valid evidence
  model: string | null;
  screen_model?: string | null;
  threshold: number | null;
  sources: string[];
  clips: string[];
  gpu?: string | null;
  analyse_fps?: number | null;
}

export interface BenchmarkAggregate {
  sources: number;
  events: number;
  non_event_hours: number;
  event_recall_step1: number | null;
  event_recall_final: number | null;
  event_recall_final_ci95: [number, number];
  false_per_hour_step1: number | null;
  false_per_hour_final: number | null;
  ai_filter_rate: number | null;
  verify_errors: number;
  event_to_candidate_p50_s: number | null;
  event_to_candidate_p90_s: number | null;
  step1_wall_p50_s: number | null;
  step1_wall_p90_s: number | null;
  candidate_to_verified_p50_s: number | null;
  candidate_to_verified_p90_s: number | null;
  push_s: number;
  detection_to_card_p50_s: number | null;
  detection_to_card_p90_s: number | null;
}

export type DemoOutcome = "detected" | "missed" | "rejected_by_ai" | "false_alarm" | "filtered_by_ai" | "clean";

export interface DemoRow {
  camera_id: string;
  clip: string;
  expected_event: { start: number; end: number } | null;
  outcome: DemoOutcome;
  result: Record<string, unknown>;
}

export interface BenchmarkReport {
  meta: ReportMeta;
  test: { aggregate: BenchmarkAggregate; per_source: unknown[] } | null;
  demo: { per_clip: DemoRow[] } | null;
}

export interface ScaleRow {
  n: number;
  fps_mean: number | null;
  fps_min: number | null;
  lag_p90_s: number | null;
  gpu_mem_gb: number | null;
  ok: boolean;
  oom?: boolean;
  error?: string;
}

export interface ScaleReport {
  meta: ReportMeta;
  target_fps: number;
  rows: ScaleRow[];
  max_cameras_ok: number;
  stopped_reason?: string | null;
}

export interface ReportsResponse {
  benchmark: BenchmarkReport | null;
  scale: ScaleReport | null;
  baseline: { time_to_notice_s: number | null; source: string | null } | null;
  feedback_rows: number;
  generated_hint: string;
}
