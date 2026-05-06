import type {
  AnalysisResults,
  CalibrationConfig,
  RunRequest,
  SessionState
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json() as Promise<T>;
}

export function createSession(name?: string): Promise<SessionState> {
  return request<SessionState>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ name: name || undefined })
  });
}

export function saveCalibration(
  sessionId: string,
  calibration: CalibrationConfig
): Promise<SessionState> {
  return request<SessionState>(`/api/sessions/${sessionId}/calibration`, {
    method: "POST",
    body: JSON.stringify(calibration)
  });
}

export function runAnalysis(sessionId: string, payload: RunRequest): Promise<SessionState> {
  return request<SessionState>(`/api/sessions/${sessionId}/run`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchResults(sessionId: string): Promise<AnalysisResults> {
  return request<AnalysisResults>(`/api/sessions/${sessionId}/results`);
}

export function socketUrl(sessionId: string): string {
  const base = API_BASE || window.location.origin;
  return `${base.replace(/^http/, "ws")}/ws/sessions/${sessionId}`;
}
