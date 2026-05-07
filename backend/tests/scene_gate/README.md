# SceneGate test flow

This directory contains the runnable M2a SceneGate sample flow.

## Run test001

From the repository root:

```bash
.venv/bin/python backend/tests/scene_gate/run_test001.py
```

Default input:

```text
data/samples/test001.mp4
```

Default outputs:

```text
data/exports/scene_gate/test001_scene_gate.json
data/exports/scene_gate/test001_validation_template.md
data/exports/scene_gate/test001_roi_preview.jpg
data/exports/scene_gate/test001_scene_gate_eval.json
data/exports/scene_gate/test001_scene_gate_eval.md
```

The JSON file is the automated output. It contains a primary `idle` / `rally`
timeline plus nested `smash_candidate` intervals inside rally segments. The
markdown file is a manual review template because the current baseline still
needs a person to confirm whether visible rally and smash intervals were
retained. The preview image shows the ROI used by the automated run.

If `data/samples/manual_scene` exists, the script also evaluates generated
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
data/exports/scene_gate/test001_scene_gate_eval.json
data/exports/scene_gate/test001_scene_gate_eval.md
```

The report includes interval precision, recall, F1, tolerant IoU, manual hit
rate, missed manual intervals, and false-positive intervals.

## Model spike workflow

The motion baseline is now treated as a comparison baseline, not the target
algorithm. For SoloShuttlePose, TrackNetV3, or a hitting-event detector:

1. Run the external project offline against `data/samples/test001.mp4`.
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
data/exports/scene_gate/soloshuttlepose/test001/artifact_manifest.json
data/exports/scene_gate/soloshuttlepose/test001/spike_report.md
data/exports/scene_gate/soloshuttlepose/test001/raw/
data/exports/scene_gate/soloshuttlepose/test001/test001_soloshuttlepose_scene_gate.json
data/exports/scene_gate/soloshuttlepose/test001/test001_soloshuttlepose_eval.json
data/exports/scene_gate/soloshuttlepose/test001/test001_soloshuttlepose_eval.md
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
`data/exports/scene_gate/soloshuttlepose/test001/spike_report.md` and avoid
rerunning the full clip until there is a reference-frame/crop strategy or a
different model baseline to test.

## Manual validation

1. Watch `data/samples/test001.mp4`.
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
