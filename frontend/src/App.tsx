import { Activity, Camera, Crosshair, Gauge, Play, Radio, Save, Video } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createSession, fetchResults, runAnalysis, saveCalibration, socketUrl } from "./api";
import type {
  AnalysisResults,
  KeyframeEvent,
  Point2D,
  SessionState,
  SocketEvent,
  SourceType,
  SpeedSample,
  TrajectoryPoint
} from "./types";

const defaultImagePoints: Point2D[] = [
  { x: 120, y: 90 },
  { x: 980, y: 110 },
  { x: 1030, y: 650 },
  { x: 80, y: 640 }
];

function optionalNumber(value: string): number | undefined {
  if (!value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export default function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [sourceType, setSourceType] = useState<SourceType>("video_file");
  const [videoPath, setVideoPath] = useState("");
  const [cameraIndex, setCameraIndex] = useState("0");
  const [fps, setFps] = useState("240");
  const [maxFrames, setMaxFrames] = useState("3000");
  const [sampleStride, setSampleStride] = useState("1");
  const [imagePoints, setImagePoints] = useState<Point2D[]>(defaultImagePoints);
  const [speedSamples, setSpeedSamples] = useState<SpeedSample[]>([]);
  const [trajectory, setTrajectory] = useState<TrajectoryPoint[]>([]);
  const [keyframes, setKeyframes] = useState<KeyframeEvent[]>([]);
  const [exports, setExports] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [socketState, setSocketState] = useState("offline");

  useEffect(() => {
    if (!session?.id) {
      return;
    }
    const ws = new WebSocket(socketUrl(session.id));
    ws.onopen = () => setSocketState("online");
    ws.onclose = () => setSocketState("offline");
    ws.onerror = () => setSocketState("error");
    ws.onmessage = (message) => {
      const event = JSON.parse(message.data) as SocketEvent;
      handleSocketEvent(event);
    };
    return () => ws.close();
  }, [session?.id]);

  const latestSample = speedSamples.length > 0 ? speedSamples[speedSamples.length - 1] : undefined;
  const latestSpeed = latestSample?.speed_kmh ?? session?.latest_speed_kmh ?? 0;
  const peakSpeed = useMemo(
    () => speedSamples.reduce((max, sample) => Math.max(max, sample.speed_kmh), 0),
    [speedSamples]
  );

  function handleSocketEvent(event: SocketEvent) {
    if (event.type === "session_status") {
      setSession(event.payload);
      if (event.payload.error) {
        setError(event.payload.error);
      }
      return;
    }
    if (event.type === "analysis_results" || event.type === "analysis_complete") {
      applyResults(event.payload);
      return;
    }
    if (event.type === "trajectory_point") {
      setTrajectory((items) => [...items.slice(-499), event.payload]);
      return;
    }
    if (event.type === "speed_sample") {
      setSpeedSamples((items) => [...items.slice(-399), event.payload]);
      return;
    }
    if (event.type === "keyframe_event") {
      setKeyframes((items) => [...items.slice(-49), event.payload]);
      return;
    }
    if (event.type === "analysis_error") {
      setError(event.payload.message);
    }
  }

  function applyResults(results: AnalysisResults) {
    setTrajectory(results.trajectory_points);
    setSpeedSamples(results.speed_samples);
    setKeyframes(results.keyframes);
    setExports(results.exports);
  }

  async function ensureSession(): Promise<SessionState> {
    if (session) {
      return session;
    }
    const created = await createSession("court-demo");
    setSession(created);
    return created;
  }

  async function handleCreateSession() {
    setError(null);
    const created = await createSession("court-demo");
    setSession(created);
    setSpeedSamples([]);
    setTrajectory([]);
    setKeyframes([]);
    setExports({});
  }

  async function handleSaveCalibration() {
    setError(null);
    const activeSession = await ensureSession();
    const updated = await saveCalibration(activeSession.id, {
      image_points: imagePoints,
      fps: optionalNumber(fps),
      court_profile: "badminton_doubles",
      court_width_m: 6.1,
      court_length_m: 13.4
    });
    setSession(updated);
  }

  async function handleRun() {
    setError(null);
    const activeSession = await ensureSession();
    const calibrated = await saveCalibration(activeSession.id, {
      image_points: imagePoints,
      fps: optionalNumber(fps),
      court_profile: "badminton_doubles",
      court_width_m: 6.1,
      court_length_m: 13.4
    });
    setSession(calibrated);
    setSpeedSamples([]);
    setTrajectory([]);
    setKeyframes([]);
    setExports({});

    const source =
      sourceType === "video_file"
        ? {
            source_type: "video_file" as const,
            path: videoPath,
            fps: optionalNumber(fps)
          }
        : {
            source_type: "camera" as const,
            camera_index: Number(cameraIndex) || 0,
            fps: optionalNumber(fps)
          };

    const running = await runAnalysis(activeSession.id, {
      source,
      max_frames: optionalNumber(maxFrames),
      sample_stride: Math.max(1, Number(sampleStride) || 1),
      save_keyframes: true
    });
    setSession(running);
  }

  async function handleRefreshResults() {
    if (!session) {
      return;
    }
    const results = await fetchResults(session.id);
    applyResults(results);
  }

  function updatePoint(index: number, axis: keyof Point2D, value: string) {
    const next = imagePoints.map((point, pointIndex) =>
      pointIndex === index ? { ...point, [axis]: Number(value) || 0 } : point
    );
    setImagePoints(next);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>Smash Suite</h1>
          <span className="subtle">Badminton speed lab</span>
        </div>
        <div className={`connection ${socketState}`}>
          <Radio size={16} />
          <span>{socketState}</span>
        </div>
      </header>

      <main className="workspace">
        <section className="panel controls">
          <div className="section-title">
            <Gauge size={18} />
            <h2>Session</h2>
          </div>
          <div className="session-row">
            <button className="primary-button" onClick={handleCreateSession}>
              <Crosshair size={16} />
              <span>New</span>
            </button>
            <div className="status-block">
              <span className="label">ID</span>
              <strong>{session?.id ?? "none"}</strong>
            </div>
            <div className="status-block">
              <span className="label">Status</span>
              <strong>{session?.status ?? "idle"}</strong>
            </div>
          </div>

          <div className="section-title">
            <Video size={18} />
            <h2>Source</h2>
          </div>
          <div className="segmented">
            <button
              className={sourceType === "video_file" ? "active" : ""}
              onClick={() => setSourceType("video_file")}
            >
              <Video size={15} />
              <span>File</span>
            </button>
            <button
              className={sourceType === "camera" ? "active" : ""}
              onClick={() => setSourceType("camera")}
            >
              <Camera size={15} />
              <span>Camera</span>
            </button>
          </div>
          {sourceType === "video_file" ? (
            <label className="field">
              <span>Local video path</span>
              <input
                value={videoPath}
                onChange={(event) => setVideoPath(event.target.value)}
                placeholder="/absolute/path/to/high-fps.mp4"
              />
            </label>
          ) : (
            <label className="field">
              <span>Camera index</span>
              <input value={cameraIndex} onChange={(event) => setCameraIndex(event.target.value)} />
            </label>
          )}
          <div className="grid-two">
            <label className="field">
              <span>FPS</span>
              <input value={fps} onChange={(event) => setFps(event.target.value)} />
            </label>
            <label className="field">
              <span>Max frames</span>
              <input value={maxFrames} onChange={(event) => setMaxFrames(event.target.value)} />
            </label>
          </div>
          <label className="field">
            <span>Sample stride</span>
            <input value={sampleStride} onChange={(event) => setSampleStride(event.target.value)} />
          </label>

          <div className="section-title">
            <Crosshair size={18} />
            <h2>Calibration</h2>
          </div>
          <div className="point-grid">
            {imagePoints.map((point, index) => (
              <div className="point-row" key={index}>
                <span>P{index + 1}</span>
                <input
                  aria-label={`P${index + 1} X`}
                  value={point.x}
                  onChange={(event) => updatePoint(index, "x", event.target.value)}
                />
                <input
                  aria-label={`P${index + 1} Y`}
                  value={point.y}
                  onChange={(event) => updatePoint(index, "y", event.target.value)}
                />
              </div>
            ))}
          </div>
          <div className="button-row">
            <button onClick={handleSaveCalibration}>
              <Save size={16} />
              <span>Save</span>
            </button>
            <button className="primary-button" onClick={handleRun}>
              <Play size={16} />
              <span>Run</span>
            </button>
            <button onClick={handleRefreshResults}>
              <Activity size={16} />
              <span>Results</span>
            </button>
          </div>
          {error && <div className="error-box">{error}</div>}
        </section>

        <section className="panel monitor">
          <div className="readout-grid">
            <Metric label="Current" value={latestSpeed.toFixed(1)} unit="km/h" />
            <Metric label="Peak" value={peakSpeed.toFixed(1)} unit="km/h" />
            <Metric label="Samples" value={String(speedSamples.length)} unit="" />
            <Metric label="Points" value={String(trajectory.length)} unit="" />
          </div>

          <div className="chart-panel">
            <div className="section-title">
              <Activity size={18} />
              <h2>Speed Curve</h2>
            </div>
            <SpeedChart samples={speedSamples} />
          </div>

          <div className="tables">
            <div>
              <h3>Keyframes</h3>
              <div className="table-list">
                {keyframes.slice(-8).map((event) => (
                  <div className="table-row" key={`${event.frame_id}-${event.time_ms}`}>
                    <span>{event.frame_id}</span>
                    <span>{event.reason}</span>
                    <strong>{event.confidence.toFixed(2)}</strong>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h3>Exports</h3>
              <div className="table-list">
                {Object.entries(exports).map(([kind, path]) => (
                  <div className="table-row" key={kind}>
                    <span>{kind}</span>
                    <strong className="path-text">{path}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function Metric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {unit && <em>{unit}</em>}
    </div>
  );
}

function SpeedChart({ samples }: { samples: SpeedSample[] }) {
  const width = 760;
  const height = 260;
  const padding = 32;
  const maxSpeed = Math.max(120, ...samples.map((sample) => sample.speed_kmh));
  const minTime = samples[0]?.time_ms ?? 0;
  const latestSample = samples.length > 0 ? samples[samples.length - 1] : undefined;
  const maxTime = latestSample?.time_ms ?? minTime + 1;
  const points = samples
    .map((sample) => {
      const x =
        padding +
        ((sample.time_ms - minTime) / Math.max(1, maxTime - minTime)) * (width - padding * 2);
      const y = height - padding - (sample.speed_kmh / maxSpeed) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg className="speed-chart" viewBox={`0 0 ${width} ${height}`} role="img">
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} />
      <line x1={padding} y1={padding} x2={padding} y2={height - padding} />
      <text x={padding} y={24}>{`${maxSpeed.toFixed(0)} km/h`}</text>
      <text x={width - 128} y={height - 10}>{`${((maxTime - minTime) / 1000).toFixed(1)} s`}</text>
      {samples.length > 1 ? (
        <polyline points={points} />
      ) : (
        <text className="empty-chart" x={width / 2 - 54} y={height / 2}>
          No samples
        </text>
      )}
    </svg>
  );
}
