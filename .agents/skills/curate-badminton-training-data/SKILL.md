---
name: curate-badminton-training-data
description: Download confirmed badminton sources, extract and validate native-rate Rally test clips, or curate reviewed court and people annotations.
---

# Curate Badminton Training Data

Keep this directory as the canonical skill. Use `scripts/run.py` for the existing
CLI; it manages its ignored Python 3.10+ environment.

## Start once per task

Run from the repository root before searching or downloading:

```bash
python3 .agents/skills/curate-badminton-training-data/scripts/run.py status
python3 .agents/skills/curate-badminton-training-data/scripts/run.py rally-status
```

Inspect cached sources, local originals/clips and durable human decisions.
Reuse completed checks and files. Do not override a human rejection without an
explicit user decision. Cache access failures separately from suitability;
recheck when the user requests download/retry, not on every handoff.

Use public, cookie-free, non-DRM formats. Chrome request impersonation is allowed;
do not log in, read browser cookies or bypass access controls. Internal source
discovery does not require a separate license-screening workflow. Keep media
and raw download metadata under ignored `datasets/badminton-v1/local/`; track
source identity, decisions, windows, checksums and results, not signed CDN URLs.
Read [schema](references/schema.md) before changing manifests, labels, imports or split rules.

## Choose the workflow

- **Find candidates:** use [source finding](../find-badminton-rally-videos/SKILL.md)
  for searches, uploader expansion and continuity inspection.
- **Download complete originals / MP4:** follow [video acquisition](references/video-acquisition.md)
  when requested. Reuse existing verified files; preserve audio and native timing.
- **Rally test clips:** follow the workflow below. Court geometry, people
  annotations and phone proof are not prerequisites.
- **Court/people annotations:** read [annotation workflow](references/annotations.md)
  only for that task.

## Rally test clips

Use the [current requirements](../../../docs/plan/rally-segmentation-requirement.md#回合算法测试视频)
and [roadmap](../../../docs/plan/roadmap.md), not counts copied into this skill.
Confirm sources/categories with the human, then choose continuous play-and-break
windows. Keep related sources/capture sessions together when separating tuning
from acceptance; prior diagnostic footage is not fresh acceptance evidence.

```bash
python3 .agents/skills/curate-badminton-training-data/scripts/run.py sample-rally \
  --url VIDEO_URL --input LOCAL_MP4 --sample-id SAMPLE_ID \
  --group personal --match-type singles --view-id VENUE_CAMERA_ID --window 120:300
python3 .agents/skills/curate-badminton-training-data/scripts/run.py review-rally \
  --sample-id SAMPLE_ID --decision accepted --reviewer codex \
  --reason "Fixed main court; continuous play and breaks in the reviewed window"
```

Omit `--input` for remote collection. Current `sample-rally` accepts 60–300 seconds,
prefers public formats up to 1080p and requires output of at least 24fps,
removes audio and generates a contact sheet. This is a tool limit, not a required
clip length; it is different from preserving audio in complete originals.
See [acquisition](references/video-acquisition.md) for re-encoding/timing limits,
source/part checks and complete decoding before treating clips as benchmark inputs.

Review the actual window for cuts and camera movement using the search skill's
inspection criteria. Keep low views, occlusion and adjacent courts as challenges
when framing is stable. After excluding damaged or cut regions, record separate
continuous source ranges and time mappings; do not stitch over missing time.

`review-rally` is an agent suitability decision, not human source approval,
court verification or rally labels. Device is unknown unless evidenced by the
source; do not infer a phone from amateur framing. Records live in
`manifests/rally-samples.json`, media/logs in `local/rally/<sample_id>/`.

Report actual categories, non-overlapping approved duration, capture families,
paths and remaining gaps. `rally-status` still reports legacy official/personal
and six-per-group `target_met`; it does not validate current four-category coverage.
