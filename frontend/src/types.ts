export type SessionStatus =
  | "created"
  | "calibrated"
  | "running"
  | "completed"
  | "failed"
  | "stopped";

export type SourceType = "video_file" | "camera";

export interface Point2D {
  x: number;
  y: number;
}

export interface CalibrationConfig {
  image_points: Point2D[];
  world_points?: Point2D[];
  fps?: number;
  court_profile?: string;
  court_width_m?: number;
  court_length_m?: number;
}

export interface SourceConfig {
  source_type: SourceType;
  path?: string;
  camera_index?: number;
  fps?: number;
}

export interface RunRequest {
  source: SourceConfig;
  max_frames?: number;
  sample_stride: number;
  save_keyframes: boolean;
}

export interface SessionState {
  id: string;
  name: string;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
  calibration?: CalibrationConfig | null;
  source?: SourceConfig | null;
  latest_speed_kmh?: number | null;
  result_count: number;
  error?: string | null;
}

export interface TrajectoryPoint {
  frame_id: number;
  time_ms: number;
  pixel: Point2D;
  world?: Point2D | null;
  confidence: number;
  source: string;
}

export interface SpeedSample {
  time_ms: number;
  speed_kmh: number;
  confidence: number;
  frame_start: number;
  frame_end: number;
}

export interface KeyframeEvent {
  time_ms: number;
  frame_id: number;
  reason: string;
  confidence: number;
  clip_path?: string | null;
}

export interface AnalysisResults {
  session_id: string;
  trajectory_points: TrajectoryPoint[];
  speed_samples: SpeedSample[];
  keyframes: KeyframeEvent[];
  exports: Record<string, string>;
}

export type SocketEvent =
  | { type: "session_status"; payload: SessionState }
  | { type: "analysis_results"; payload: AnalysisResults }
  | { type: "analysis_complete"; payload: AnalysisResults }
  | { type: "trajectory_point"; payload: TrajectoryPoint }
  | { type: "speed_sample"; payload: SpeedSample }
  | { type: "keyframe_event"; payload: KeyframeEvent }
  | { type: "analysis_error"; payload: { message: string } };
