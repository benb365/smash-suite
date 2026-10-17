# Court and people annotation workflow

Read only for annotation work. This does not gate Rally source collection.
The [schema](schema.md) owns record fields, geometry rules and training/split
coverage requirements; [tooling](tooling.md) covers optional model invocation.

## Collect and review

1. Use the collector's preflight. Search small batches for a `court` or `people`
   purpose with `record-search`; reuse its 30-day cache. Use broadcast footage
   mainly for clean baselines or camera/replay negatives.
2. `preview` downloads bounded windows. Its failures are cached for seven days;
   use `--retry` only after an explicit retry decision, not automatic repetition.
3. Have a human review the contact sheet, capture context, competition level,
   stable `view_id` and `split_group_id`, then record `review-source`.
   Human source and court-fit decisions require an explicit decision and
   `--recheck` to replace.
4. `sample-court` collects a few complete-court frames per independent view;
   add partial/negative frames for distinct failure modes, not volume.
5. For optional model point proposals, save exact raw output and producer/model/
   version/prompt/frame hash using `record-court-proposal`; reuse cached proposals.
   Render with `render-court-proposal` before human review.
6. Keep immutable proposals and separate review sidecars. `needs_review` may
   retain corrections but produces no draft labels; `rejected` carries none.
   Only explicit human `accepted` with at least four non-collinear, non-uncertain
   controls may run `review-court-proposal` and produce model-assisted drafts.
7. Use `build-cvat` / `import-cvat` for manual correction when useful. Run
   `fit-court`, inspect the overlay and record `review-court-fit`; do not accept
   underconstrained geometry.
8. Only after verified geometry for that view, `sample-people` collects bounded
   clips for annotation. Run `validate` before training or splitting.

## Annotation invariants

- Keep manual and `geometry_inferred` court points separate; inferred points
  require verified review plus explicit `--allow-inferred-training`.
- Model output is a proposal, not a label. Human-accepted model points carry
  `annotation_origin=model_assisted_human_verified`.
- Label `person`, not `participant`; track people on playing/officiating areas
  with role and court side, excluding seated stands. Keep identities within a
  continuous clip; do not export this as a generic person detector dataset.
- A venue-camera setup is the diversity unit. Related views/sessions stay in
  one split. Keep `local/ysp/test_ysp.ts` held out from training.
- The geometry pilot and model coverage floors in the schema validate stages,
  not data sufficiency; do not turn them into prerequisites for Rally tests.

Use the existing CLI's `--help` for arguments. `--dataset-root` precedes the
subcommand for isolated work; sampling can use `--input LOCAL_VIDEO`.
