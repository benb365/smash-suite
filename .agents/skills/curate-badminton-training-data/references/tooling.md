# Reused tools

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) and FFmpeg: follow
  [video acquisition](video-acquisition.md) for bounded previews, requested
  complete originals, MP4 remuxing and native-timing checks.
- [CVAT CLI](https://docs.cvat.ai/docs/api_sdk/cli/): create/upload tasks
  from the generated labels and media bundle rather than building an
  annotation UI.
- [Datumaro format](https://opencv.github.io/cvat/docs/manual/advanced/formats/format-datumaro/):
  use as the annotation exchange format.
- [NumPy](https://numpy.org/): use normalized DLT/SVD for deterministic court
  homography fitting from reviewed control points.
- [Pillow](https://pillow.readthedocs.io/): render local fit overlays for human
  review; it does not decide whether a fit is accepted.
- Vision models may propose visible court points, but provider invocation stays
  outside the deterministic CLI. Save compact JSON with exact producer, model,
  model version, prompt version, confidence, uncertainty, and frame hash through
  `record-court-proposal`. Never rerun an identical cached proposal or promote
  it without explicit human review.
- On this workstation, invoke Claude Code directly with
  `claude --model Doubao-Seed-2.1-turbo`; use the CCR bridge only if the direct
  client is unavailable. This explicit model selection is required for image
  input; the default Agent Plan model is text-only. Treat any JSON output
  exactly like another immutable model proposal. If authentication fails, the
  active model rejects image input, or the service returns an explicit failure,
  stop the attempt and leave the frame for human review. Long multimodal latency
  alone is not a failure: do not impose a fixed timeout. Never convert local
  line-detection output into accepted controls without visual confirmation.
  Current `Doubao-Seed-2.1-turbo` trials identify court semantics more reliably
  than exact pixels; always render its coordinates over the original-resolution
  frame before review.
- [Fine-Badminton](https://zenodo.org/records/20292976): metadata reference
  for internal non-commercial research. Do not download the complete dataset
  through this skill.
