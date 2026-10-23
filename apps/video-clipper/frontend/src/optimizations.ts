import type { CameraType, Optimizations } from './types';

export type SavedOptimizations = Partial<Record<CameraType, Partial<Optimizations>>>;

export function defaultOptimizations(camera: CameraType): Optimizations {
  return { limit_fps: true, small_input: true, grayscale: true, dynamic_scan: camera === 'high' };
}

export function resolveOptimizations(camera: CameraType, saved?: Partial<Optimizations>): Optimizations {
  const defaults = defaultOptimizations(camera);
  return {
    limit_fps: typeof saved?.limit_fps === 'boolean' ? saved.limit_fps : defaults.limit_fps,
    small_input: typeof saved?.small_input === 'boolean' ? saved.small_input : defaults.small_input,
    grayscale: typeof saved?.grayscale === 'boolean' ? saved.grayscale : defaults.grayscale,
    dynamic_scan: typeof saved?.dynamic_scan === 'boolean' ? saved.dynamic_scan : defaults.dynamic_scan,
  };
}

export type SessionPreferences = {
  camera?: CameraType;
  quality?: 'high' | 'balanced' | 'small';
  court?: [number, number][];
  optimizationsByCamera?: SavedOptimizations;
};

export type SessionSnapshot = { id: string; token: string; preferences?: SessionPreferences };
