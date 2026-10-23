export type CameraType = 'high' | 'courtside' | 'personal';
export type Quality = 'high' | 'balanced' | 'small';
export type Point = [number, number];
export interface JobState {
  status: 'empty' | 'uploading' | 'ready' | 'running' | 'completed' | 'failed' | 'cancelled';
  stage: string;
  progress: number;
  video: { name: string; duration_ms: number; width: number; height: number; has_audio: boolean } | null;
  output_url: string | null;
  output_bytes: number | null;
  output_duration_ms: number | null;
  rally_count: number;
  elapsed_s: number | null;
  timings: { preparation_s: number; recognition_s: number; rendering_s: number } | null;
  error: string | null;
  warnings: string[];
}
export interface ScreenState {
  job: JobState;
  online: boolean;
  uploadProgress: number;
  saving: boolean;
  camera: CameraType;
  showShotPaths: boolean;
  quality: Quality;
  court: Point[];
  selectingCourt: boolean;
  notice: string;
  error: string;
  canSave: boolean;
}
export const emptyJob: JobState = {
  status: 'empty', stage: '选择一份 MP4 录像开始', progress: 0, video: null,
  output_url: null, output_bytes: null, output_duration_ms: null, rally_count: 0,
  elapsed_s: null, timings: null, error: null, warnings: [],
};
export const initialScreen: ScreenState = {
  job: emptyJob, online: false, uploadProgress: 0, saving: false, camera: 'high',
  showShotPaths: true, quality: 'balanced', court: [], selectingCourt: false, notice: '', error: '', canSave: true,
};
