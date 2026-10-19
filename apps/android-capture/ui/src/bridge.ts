// Platform implementations keep media files, credentials and retry state native.
// iOS can reuse this interface and the page with its own capture service.
export interface CaptureState {
  recording: boolean;
  starting: boolean;
  stopping: boolean;
  pendingSegments: number;
  pendingBytes: number;
  uploadedSegments: number;
  endpoint: string;
  lastError: string;
  lastUploadLatencyMs: number;
  oldestPendingAgeMs: number;
  interruptedParts: number;
  warning: string;
}

declare const NativeModules: {
  Capture: {
    getState(callback: (json: string) => void): void;
    command(command: 'start' | 'stop' | 'settings' | 'retry'): void;
  };
};

export const capture = {
  read(callback: (state: CaptureState) => void) {
    NativeModules.Capture.getState((json) => callback(JSON.parse(json) as CaptureState));
  },
  command(command: 'start' | 'stop' | 'settings' | 'retry') {
    NativeModules.Capture.command(command);
  },
};
