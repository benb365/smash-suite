# SceneGate test flow

This directory contains the runnable M2a SceneGate sample flow.

## Run test001

From the repository root:

```bash
.venv/bin/python backend/tests/scene_gate/run_test001.py
```

Default input:

```text
datasets/badminton-v1/local/test001/test001.mp4
```

Default outputs:

```text
backend/tests/scene_gate/.runtime/test001_scene_gate.json
backend/tests/scene_gate/.runtime/test001_validation_template.md
backend/tests/scene_gate/.runtime/test001_roi_preview.jpg
backend/tests/scene_gate/.runtime/test001_scene_gate_eval.json
backend/tests/scene_gate/.runtime/test001_scene_gate_eval.md
```

The JSON file is the automated output. It contains a primary `idle` / `rally`
timeline plus nested `smash_candidate` intervals inside rally segments. The
markdown file is a manual review template because the current baseline still
needs a person to confirm whether visible rally and smash intervals were
retained. The preview image shows the ROI used by the automated run.

If `datasets/badminton-v1/annotations/seed/test001/manual_scene` exists, the script also evaluates generated
`rally` intervals against the manual labels and writes the two evaluation files.
The current manual labels have roughly 1s boundary noise, so the default
evaluation tolerance is 1000ms.

Useful overrides:

```bash
.venv/bin/python backend/tests/scene_gate/run_test001.py --sample-stride 1
.venv/bin/python backend/tests/scene_gate/run_test001.py --max-frames 1200
.venv/bin/python backend/tests/scene_gate/run_test001.py --no-default-roi
.venv/bin/python backend/tests/scene_gate/run_test001.py --roi-polygon '[[0,1],[1,1],[1,0.53],[0,0.54]]'
.venv/bin/python backend/tests/scene_gate/run_test001.py --min-rally-ms 6000 --min-idle-ms 4000
.venv/bin/python backend/tests/scene_gate/run_test001.py --skip-evaluation
```

## Evaluate manual_scene only

After a SceneGate JSON exists, run:

```bash
.venv/bin/python backend/tests/scene_gate/evaluate_manual_scene.py
```

This emits:

```text
backend/tests/scene_gate/.runtime/test001_scene_gate_eval.json
backend/tests/scene_gate/.runtime/test001_scene_gate_eval.md
```

The report includes interval precision, recall, F1, tolerant IoU, manual hit
rate, missed manual intervals, and false-positive intervals.

## Model spike workflow

The motion baseline is now treated as a comparison baseline, not the target
algorithm. For SoloShuttlePose, TrackNetV3, or a hitting-event detector:

1. Run the external project offline against `datasets/badminton-v1/local/test001/test001.mp4`.
2. Convert its rally or event output into `SceneSegment`-compatible intervals.
3. Reuse `evaluate_manual_scene.py` or the same metric functions in
   `backend/app/vision/scene_eval.py`.
4. Compare precision, recall, F1, manual hit rate, runtime, and setup friction
   before deciding whether to integrate the model.

No extra Codex Skill is needed yet; the repo-local scripts and this README are
enough until an external model runner is actually integrated.

## SoloShuttlePose PC spike

SoloShuttlePose is an external PC-only dependency for this spike. Keep it out of
the Smash Suite repo history:

```bash
git clone https://github.com/sunwuzhou03/SoloShuttlePose models/SoloShuttlePose
```

If cloning is slow, a downloaded GitHub archive is also fine as long as it is
unpacked to:

```text
models/SoloShuttlePose
```

Follow the upstream Quick Start to create its environment and download weights.
The upstream doc says to place the weight folder under:

```text
models/SoloShuttlePose/src/model
```

However, the current upstream source code loads these runtime files from
`models/SoloShuttlePose/src/models/weights`:

```text
court_kpRCNN.pth
net_kpRCNN.pth
pose_kpRCNN.pth
ball_track.pt
```

Place, copy, or symlink the downloaded files so those runtime paths exist before
running the spike. The local `test001` spike used the downloaded archive
`~/Downloads/weights-20260507T110316Z-3-001.zip`; extract only these four files
to avoid duplicating large model artifacts on disk.

Then run:

```bash
.venv/bin/python backend/tests/scene_gate/run_soloshuttlepose_test001.py
```

If SoloShuttlePose needs a different Python or conda environment:

```bash
SOLOSHUTTLEPOSE_PYTHON=/path/to/solo/env/bin/python \
  .venv/bin/python backend/tests/scene_gate/run_soloshuttlepose_test001.py
```

Default outputs:

```text
models/SoloShuttlePose/.runtime/soloshuttlepose/test001/artifact_manifest.json
models/SoloShuttlePose/.runtime/soloshuttlepose/test001/spike_report.md
models/SoloShuttlePose/.runtime/soloshuttlepose/test001/raw/
models/SoloShuttlePose/.runtime/soloshuttlepose/test001/test001_soloshuttlepose_scene_gate.json
models/SoloShuttlePose/.runtime/soloshuttlepose/test001/test001_soloshuttlepose_eval.json
models/SoloShuttlePose/.runtime/soloshuttlepose/test001/test001_soloshuttlepose_eval.md
```

The adapter can parse upstream `VideoClip` rally outputs named
`res/videos/<video>/<video>_<begin>-<end>.mp4`; it uses the matching video
metadata JSON `fps` to convert frame ranges into `SceneSegment` rally intervals.
The converted SceneGate JSON and eval files are only created when the adapter can
parse rally-like intervals from SoloShuttlePose artifacts. If the report says
`needs_converter`, inspect `raw/` and extend `backend/app/vision/soloshuttlepose_adapter.py`
for any additional output format. If it says `blocked`, install the external repo
and weights first.

Current `test001` result: the SoloShuttlePose runtime weights load successfully,
but upstream court preprocessing fails after scanning almost the full 9269-frame
video, so no rally clip is produced. The CPU run was stopped during net
preprocessing to conserve local resources. Keep the evidence in
`models/SoloShuttlePose/.runtime/soloshuttlepose/test001/spike_report.md` and avoid
rerunning the full clip until there is a reference-frame/crop strategy or a
different model baseline to test.

## test_ysp rally segmentation simulator

The current fixed-camera rally segmentation route is implemented as a streaming
simulator plus YOLO + ByteTrack person tracking and a rally state machine. It
processes frames in timestamp order and emits only
`SceneSegment(category="rally")` intervals.

Default smoke run:

```bash
.venv/bin/python backend/tests/scene_gate/run_test_ysp_rally_segmentation.py --max-frames 250
```

Default input:

```text
datasets/badminton-v1/local/ysp/test_ysp.ts
datasets/badminton-v1/annotations/seed/ysp/ROI.json
```

Default output:

```text
models/yolo11n/.runtime/scene_gate/test_ysp_rally_segmentation.json
models/yolo11n/.runtime/scene_gate/test_ysp_rally_segmentation_perf.json
models/yolo11n/.runtime/scene_gate/test_ysp_rally_segmentation_trace.jsonl
```

To also render sampled detector frames with ROI, person boxes, track ids, foot
points, and active-state text:

```bash
.venv/bin/python backend/tests/scene_gate/run_test_ysp_rally_segmentation.py \
  --sample-stride 10 \
  --write-debug-video
```

Debug video output:

```text
models/yolo11n/.runtime/scene_gate/test_ysp_rally_segmentation_debug.mp4
```

The trace JSONL contains one line per analyzed frame. Each line records source
`frame_id`, source `time_ms`, raw detections, ByteTrack tracks, selected main
track ids, signal values such as `max_foot_speed_px_s` and
`max_foot_acceleration_px_s2`, state transitions, and any emitted segments.
After reviewing the trace, rerun only the state machine without YOLO inference:

```bash
.venv/bin/python backend/tests/scene_gate/run_test_ysp_rally_segmentation.py \
  --replay-trace models/yolo11n/.runtime/scene_gate/test_ysp_rally_segmentation_trace.jsonl \
  --sample-stride 10 \
  --output models/yolo11n/.runtime/scene_gate/test_ysp_rally_segmentation_replay.json
```

The current default state-machine parameters are recall-oriented:
`active-speed-px-s=60`, `active-acceleration-px-s2=80`,
`stable-visible-ms=0`, `start-guard-ms=5000`, `end-guard-ms=1600`,
`active-window-ms=400`, `merge-gap-ms=8000`, and `min-rally-ms=1000`.
Override them on either a full run or a trace replay, for example:

```bash
.venv/bin/python backend/tests/scene_gate/run_test_ysp_rally_segmentation.py \
  --replay-trace models/yolo11n/.runtime/scene_gate/test_ysp_rally_segmentation_trace.jsonl \
  --sample-stride 10 \
  --active-speed-px-s 80 \
  --merge-gap-ms 5000
```

Boundary evaluation is deliberately opt-in because
`datasets/badminton-v1/annotations/seed/ysp/rally-segment-manual.json` is currently
`draft_needs_human_review`. After a person verifies every rally interval and
sets the top-level and per-segment statuses to `verified`, run:

```bash
.venv/bin/python backend/tests/scene_gate/run_test_ysp_rally_segmentation.py --evaluate-boundaries
```

If the annotation is still a draft, the script exits before computing boundary
metrics. This protects containment and 2s boundary-pass numbers from being
reported against AI-generated labels.

The default detector is `yolo-bytetrack`, using `yolo11n.pt` and
`bytetrack.yaml`. The first run may download the nano model through
Ultralytics. To force the lightweight fallback path:

```bash
.venv/bin/python backend/tests/scene_gate/run_test_ysp_rally_segmentation.py \
  --detector hog
```

To use a specific local YOLO weight file:

```bash
.venv/bin/python backend/tests/scene_gate/run_test_ysp_rally_segmentation.py \
  --detector yolo-bytetrack \
  --yolo-model /path/to/yolo11n.pt \
  --tracker-config bytetrack.yaml
```

## Manual validation

1. Watch `datasets/badminton-v1/local/test001/test001.mp4`.
2. Check `test001_roi_preview.jpg`; the polygon should cover the relevant court
   and exclude as much background motion as possible.
3. Fill in `test001_validation_template.md` with manual rally and smash intervals.
4. Compare manual intervals with rally segments and nested `smash_candidate`
   intervals in the JSON.
5. Record missed intervals, false positives, and occlusion-caused failures before
   changing thresholds.

Current validation is intentionally semi-automatic: OpenCV creates the timeline,
but a human still decides whether the candidate intervals preserve the important
badminton actions.

The first baseline also suppresses very large foreground motion as non-rally
noise. This is meant to avoid treating people walking through the camera view as
play, but it must be checked manually because a near-camera player can look
similar to an occluder.

The default `test001` thresholds intentionally smooth the timeline at seconds
scale (`min-rally-ms=4000`, `min-idle-ms=3000`). Saving or cutting millisecond
gaps is not useful for review or demo clips, so short gaps are bridged and short
motion blips without smash candidates are suppressed.
