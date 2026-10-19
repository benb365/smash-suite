# Dataset schema v2

The tracked root is `datasets/badminton-v1/`. Downloaded media, contact sheets,
overlays, and CVAT bundles live under ignored `local/`.

## Sources and cache

`manifests/sources.json` contains `schema_version=2` and source records:

- stable source identity, canonical URL, title, status, usage, and provenance;
- `capture_context=campus|club|personal|broadcast|other`;
- `competition_level=amateur|professional|unknown`;
- `purposes`, containing `court` and/or `people`;
- accepted sources also require a stable `view_id` and `split_group_id`;
- artifacts record target, scene, view, bounded source time, sampling, and
  SHA-256.

`view_id` identifies one fixed venue-camera setup. `split_group_id` groups views
that must remain in one train/validation/test partition, normally a venue or
capture session.

Search cache keys are `purpose:normalized query` and remain fresh for 30 days.
Legacy broadcast queries do not satisfy new court/people coverage gaps.
Preview failures remain cached for seven days to avoid repeatedly resolving an
unavailable public format; retry only after an explicit decision.

## Independent Rally test-video records

`manifests/rally-samples.json` is a separate version-1 test-video index. Each
record contains sample/source identity, canonical URL, source title/uploader,
`group=official|personal`, `match_type=singles|doubles`, independent `view_id`, bounded source window,
device evidence and creation time. Local clips and diagnostics live under
ignored `local/rally/<sample_id>/`.

Media checks record native fps, dimensions, duration, complete decoding,
SHA-256, byte count, contact-sheet path and suspected cut times. State is
`failed`, `needs_visual_review`, `accepted` or `rejected`. A suitability review
records reviewer, time, reason and whether phone recording has source evidence.
An agent suitability review never changes a human source/geometry decision or
creates rally ground truth. Count accepted independent views, not file count;
only singles count toward the current collection target. Phone confirmation
is an evidence field, not a requirement of the current four-view duration
target. The existing official/personal group is not the four-view category
classification; category confirmation and duration accounting follow the
[Rally test-video requirements](../../../../modules/rally/evaluation.md#回合算法测试视频).

## Court data

Court scenes are:

- `court_complete`: sufficient visible geometry for a complete manual label;
- `court_partial`: incomplete view that may support a reviewed geometry fit;
- `view_negative`: close-up, replay, moving camera, or non-court view;
- `court_partial_unresolved`: insufficient, degenerate, or rejected fit.

CVAT stores only certain visible `court_control_point` annotations. Point IDs
refer to known singles-court intersections at baselines, short service lines,
net endpoints, and center-line intersections.

At least four unique, non-collinear world and image points are required for a
normalized DLT fit. A proposed geometry contains:

```text
CourtGeometry(
  view_id,
  homography_image_from_court,
  canonical_points[6] {
    point_id,
    x,
    y,
    visibility: visible | occluded | outside,
    source: manual | geometry_inferred
  },
  reprojection_error,
  review_status
)
```

The six canonical points remain far baseline corners, net endpoints, and near
baseline corners. Coordinates may lie outside the image. Missing points are
never fabricated when the fit is unresolved. Verified geometry defaults to
manual-only `training_points`; inferred points require explicit reviewer opt-in.
With exactly four controls, reprojection error has no redundant evidence;
reviewers must decide from the projected template overlay.

### Model-assisted court proposals

Model output is stored below
`annotations/proposed/court/<view_id>/<proposal_id>.json`. The proposal is
immutable and records:

- sampled frame path, dimensions, and SHA-256;
- producer tool, model, model version, and prompt version;
- visible standard points with `confidence` and mandatory boolean `uncertain`;
- source/view/item identity and creation time.

The human decision is a separate `<proposal_id>.review.json` sidecar containing
the proposal hash, reviewer, reason, decision, and any corrected-input hash.
When a `needs_review` decision includes a correction, its normalized
`corrected_points` are stored in the sidecar so incomplete human work is
recoverable and auditable. `needs_review` never produces draft labels;
`rejected` carries no correction. `accepted` requires at least four unique
non-collinear controls and no remaining uncertain points.
Promotion writes `draft/court-controls/<view_id>.json` with
`annotation_origin=model_assisted_human_verified`; the original proposal stays
available for later audit. Confidence never bypasses human review.
`render-court-proposal` writes a labeled image below ignored `local/` storage;
rendering does not alter the proposal or constitute a review decision.

## People data

People scenes are `clean`, `adjacent_court`, `extra_people`, and
`occlusion_or_exit`. Each sample is a bounded 10–20 second silent clip at 10 FPS
and at most 720p. A verified geometry for the same `view_id` is mandatory.

CVAT uses a `person` rectangle track with:

- `role=participant|non_participant|unknown`;
- `court_side=near|far|outside|unknown`;
- native `track_id`, `occluded`, and `outside`.

Label discernible people on the playing floor and officiating area; ignore
seated stands. These annotations train or evaluate court-conditioned selection,
not a generic person detector.

## Targets and splits

Ten verified independent views, including eight non-broadcast views and all
three named non-broadcast contexts, are only the pipeline pilot.

The first trainable model baseline has a floor of 30 verified views, including
at least 24 non-broadcast views and 12 independent split groups. Each people
challenge type—adjacent court, extra people, and occlusion or exit—must appear
in at least five verified independent views. This floor is not an accuracy
claim. Add views in increments of ten from held-out error clusters and learning
curves.

Splits list source IDs, but validation also enforces `split_group_id`: no group
may cross train, validation, and test. `datasets/badminton-v1/local/ysp/test_ysp.ts` remains an
additional held-out benchmark.
