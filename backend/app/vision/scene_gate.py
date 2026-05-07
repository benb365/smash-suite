from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

from app.models import SceneCandidate, SceneGateResult, SceneSegment, SceneTimelineCategory


@dataclass(frozen=True)
class SceneGateConfig:
    sample_stride: int = 5
    max_frames: Optional[int] = None
    resize_width: int = 360
    diff_threshold: int = 24
    idle_motion_ratio: float = 0.035
    smash_motion_ratio: float = 0.115
    smash_component_area_ratio: float = 0.05
    occlusion_motion_ratio: float = 0.22
    occlusion_component_area_ratio: float = 0.12
    smash_pre_roll_ms: float = 800.0
    smash_post_roll_ms: float = 1200.0
    min_segment_ms: float = 250.0
    min_rally_ms: float = 4000.0
    min_idle_ms: float = 3000.0
    min_candidate_ms: float = 120.0
    merge_gap_ms: float = 250.0
    roi_polygon: Optional[Sequence[Tuple[float, float]]] = None
    roi_is_relative: bool = True

    def normalized(self) -> "SceneGateConfig":
        roi_polygon = None
        if self.roi_polygon is not None:
            roi_polygon = tuple((float(x), float(y)) for x, y in self.roi_polygon)

        return SceneGateConfig(
            sample_stride=max(1, self.sample_stride),
            max_frames=self.max_frames,
            resize_width=max(64, self.resize_width),
            diff_threshold=max(1, self.diff_threshold),
            idle_motion_ratio=max(0.0, self.idle_motion_ratio),
            smash_motion_ratio=max(0.0, self.smash_motion_ratio),
            smash_component_area_ratio=max(0.0, self.smash_component_area_ratio),
            occlusion_motion_ratio=max(0.0, self.occlusion_motion_ratio),
            occlusion_component_area_ratio=max(0.0, self.occlusion_component_area_ratio),
            smash_pre_roll_ms=max(0.0, self.smash_pre_roll_ms),
            smash_post_roll_ms=max(0.0, self.smash_post_roll_ms),
            min_segment_ms=max(0.0, self.min_segment_ms),
            min_rally_ms=max(0.0, self.min_rally_ms),
            min_idle_ms=max(0.0, self.min_idle_ms),
            min_candidate_ms=max(0.0, self.min_candidate_ms),
            merge_gap_ms=max(0.0, self.merge_gap_ms),
            roi_polygon=roi_polygon,
            roi_is_relative=self.roi_is_relative,
        )


@dataclass(frozen=True)
class FrameMetric:
    frame_id: int
    time_ms: float
    motion_ratio: float
    max_component_area_ratio: float


@dataclass(frozen=True)
class ClassifiedMetric:
    metric: FrameMetric
    category: SceneTimelineCategory
    confidence: float
    reason: str


@dataclass(frozen=True)
class CandidateWindow:
    start_ms: float
    end_ms: float
    reason: str
    peak_frame_id: int
    confidence: float


def run_scene_gate(
    video_path: Union[str, Path],
    config: Optional[SceneGateConfig] = None,
) -> SceneGateResult:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV and numpy are required for SceneGate. "
            "Run `python3 -m pip install -r backend/requirements.txt`."
        ) from exc

    scene_config = (config or SceneGateConfig()).normalized()
    source_path = Path(video_path)
    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {source_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    video_duration_ms = (frame_count / fps) * 1000.0 if frame_count else 0.0

    metrics: List[FrameMetric] = []
    previous_gray = None
    roi_mask = None
    roi_area = 0
    frame_id = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame_id += 1
            if scene_config.max_frames is not None and frame_id > scene_config.max_frames:
                break
            if frame_id % scene_config.sample_stride != 0:
                continue

            height, width = frame.shape[:2]
            scale = scene_config.resize_width / float(width)
            resized_height = max(1, int(height * scale))
            frame_small = cv2.resize(frame, (scene_config.resize_width, resized_height))
            gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            time_ms = ((frame_id - 1) / fps) * 1000.0

            if roi_mask is None:
                roi_mask = _build_roi_mask(gray.shape, scene_config, cv2, np)
                roi_area = int(np.count_nonzero(roi_mask)) if roi_mask is not None else gray.size

            if previous_gray is None:
                previous_gray = gray
                metrics.append(
                    FrameMetric(
                        frame_id=frame_id,
                        time_ms=time_ms,
                        motion_ratio=0.0,
                        max_component_area_ratio=0.0,
                    )
                )
                continue

            diff = cv2.absdiff(previous_gray, gray)
            previous_gray = gray
            if roi_mask is not None:
                diff = cv2.bitwise_and(diff, diff, mask=roi_mask)

            _, motion_mask = cv2.threshold(
                diff,
                scene_config.diff_threshold,
                255,
                cv2.THRESH_BINARY,
            )
            motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, None, iterations=1)
            contours, _ = cv2.findContours(
                motion_mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            max_area = max((float(cv2.contourArea(contour)) for contour in contours), default=0.0)
            metric_area = max(1, roi_area)
            metrics.append(
                FrameMetric(
                    frame_id=frame_id,
                    time_ms=time_ms,
                    motion_ratio=float(np.count_nonzero(motion_mask)) / metric_area,
                    max_component_area_ratio=max_area / metric_area,
                )
            )
    finally:
        cap.release()

    effective_duration_ms = _effective_duration_ms(metrics, video_duration_ms)
    segments, candidates = build_scene_timeline(metrics, scene_config, effective_duration_ms)
    category_durations_ms = _category_durations(segments)
    retained_ms = category_durations_ms.get("rally", 0.0)
    smash_candidate_ms = sum(max(0.0, item.end_ms - item.start_ms) for item in candidates)
    retained_ratio = retained_ms / effective_duration_ms if effective_duration_ms > 0 else 0.0
    smash_candidate_ratio = (
        smash_candidate_ms / effective_duration_ms if effective_duration_ms > 0 else 0.0
    )

    return SceneGateResult(
        video_path=str(source_path),
        fps=round(fps, 3),
        frame_count=frame_count,
        duration_ms=round(effective_duration_ms, 3),
        analyzed_frame_count=len(metrics),
        sample_stride=scene_config.sample_stride,
        retained_ms=round(retained_ms, 3),
        retained_ratio=round(retained_ratio, 4),
        smash_candidate_ms=round(smash_candidate_ms, 3),
        smash_candidate_ratio=round(smash_candidate_ratio, 4),
        category_durations_ms={
            category: round(duration, 3) for category, duration in category_durations_ms.items()
        },
        segments=segments,
        smash_candidates=candidates,
        config=asdict(scene_config),
    )


def build_scene_timeline(
    metrics: Sequence[FrameMetric],
    config: SceneGateConfig,
    duration_ms: float,
) -> Tuple[List[SceneSegment], List[SceneCandidate]]:
    if not metrics:
        return [], []

    scene_config = config.normalized()
    candidate_windows = _merge_candidate_windows(_candidate_windows(metrics, scene_config))
    classified = _classify_metrics(metrics, scene_config)
    raw_segments = _group_classified_metrics(classified, duration_ms)
    segments = _smooth_segments(raw_segments, scene_config, candidate_windows)
    candidates = _clip_candidates_to_rally_segments(candidate_windows, segments, metrics, scene_config)
    segments = _attach_candidates(segments, candidates)
    return segments, candidates


def build_scene_segments(
    metrics: Sequence[FrameMetric],
    config: SceneGateConfig,
    duration_ms: float,
) -> List[SceneSegment]:
    segments, _ = build_scene_timeline(metrics, config, duration_ms)
    return segments


def _classify_metrics(
    metrics: Sequence[FrameMetric],
    config: SceneGateConfig,
) -> List[ClassifiedMetric]:
    classified: List[ClassifiedMetric] = []
    for metric in metrics:
        if _is_occluded(metric, config):
            category: SceneTimelineCategory = "idle"
            reason = "large_foreground_motion_suppressed"
            confidence = 0.65
        elif metric.motion_ratio < config.idle_motion_ratio:
            category = "idle"
            reason = f"motion_ratio<{config.idle_motion_ratio:.3f}"
            confidence = _idle_confidence(metric, config)
        else:
            category = "rally"
            reason = f"motion_ratio>={config.idle_motion_ratio:.3f}"
            confidence = _rally_confidence(metric, config)

        classified.append(
            ClassifiedMetric(
                metric=metric,
                category=category,
                confidence=round(confidence, 3),
                reason=reason,
            )
        )

    return classified


def _candidate_windows(
    metrics: Sequence[FrameMetric],
    config: SceneGateConfig,
) -> List[CandidateWindow]:
    windows: List[CandidateWindow] = []
    for metric in metrics:
        if _is_occluded(metric, config):
            continue
        peak_reason = _smash_peak_reason(metric, config)
        if peak_reason is None:
            continue
        windows.append(
            CandidateWindow(
                start_ms=metric.time_ms - config.smash_pre_roll_ms,
                end_ms=metric.time_ms + config.smash_post_roll_ms,
                reason=peak_reason,
                peak_frame_id=metric.frame_id,
                confidence=round(_smash_confidence(metric, config), 3),
            )
        )
    return windows


def _smash_peak_reason(metric: FrameMetric, config: SceneGateConfig) -> Optional[str]:
    if metric.motion_ratio >= config.smash_motion_ratio:
        return f"motion_ratio>={config.smash_motion_ratio:.3f}"
    if metric.max_component_area_ratio >= config.smash_component_area_ratio:
        return f"component_area_ratio>={config.smash_component_area_ratio:.3f}"
    return None


def _is_occluded(metric: FrameMetric, config: SceneGateConfig) -> bool:
    return (
        metric.motion_ratio >= config.occlusion_motion_ratio
        or metric.max_component_area_ratio >= config.occlusion_component_area_ratio
    )


def _smash_confidence(metric: FrameMetric, config: SceneGateConfig) -> float:
    motion_score = _bounded_ratio(metric.motion_ratio, config.smash_motion_ratio)
    area_score = _bounded_ratio(metric.max_component_area_ratio, config.smash_component_area_ratio)
    return min(1.0, 0.55 + 0.45 * max(motion_score, area_score))


def _rally_confidence(metric: FrameMetric, config: SceneGateConfig) -> float:
    usable_range = max(0.001, config.smash_motion_ratio - config.idle_motion_ratio)
    score = (metric.motion_ratio - config.idle_motion_ratio) / usable_range
    return max(0.45, min(0.9, 0.45 + 0.45 * score))


def _idle_confidence(metric: FrameMetric, config: SceneGateConfig) -> float:
    if config.idle_motion_ratio == 0:
        return 0.5
    score = 1.0 - min(1.0, metric.motion_ratio / config.idle_motion_ratio)
    return max(0.45, min(0.95, 0.45 + 0.5 * score))


def _bounded_ratio(value: float, threshold: float) -> float:
    if threshold <= 0:
        return 1.0
    return max(0.0, min(1.0, value / threshold))


def _group_classified_metrics(
    classified: Sequence[ClassifiedMetric],
    duration_ms: float,
) -> List[SceneSegment]:
    if not classified:
        return []

    segments: List[SceneSegment] = []
    start_index = 0
    for index in range(1, len(classified)):
        if classified[index].category != classified[start_index].category:
            segments.append(_make_segment(classified, start_index, index, duration_ms))
            start_index = index
    segments.append(_make_segment(classified, start_index, len(classified), duration_ms))
    return segments


def _make_segment(
    classified: Sequence[ClassifiedMetric],
    start_index: int,
    end_index: int,
    duration_ms: float,
) -> SceneSegment:
    first = classified[start_index]
    last = classified[end_index - 1]
    next_time_ms = (
        classified[end_index].metric.time_ms
        if end_index < len(classified)
        else max(duration_ms, last.metric.time_ms)
    )
    segment_metrics = classified[start_index:end_index]
    confidence = sum(item.confidence for item in segment_metrics) / len(segment_metrics)
    reason = _summarize_reason(segment_metrics)
    return SceneSegment(
        category=first.category,
        start_ms=round(first.metric.time_ms, 3),
        end_ms=round(next_time_ms, 3),
        confidence=round(confidence, 3),
        reason=reason,
        source_frame_range=[first.metric.frame_id, last.metric.frame_id],
    )


def _summarize_reason(metrics: Sequence[ClassifiedMetric]) -> str:
    for metric in metrics:
        if metric.reason == "large_foreground_motion_suppressed":
            return metric.reason

    counts: dict[str, int] = {}
    for metric in metrics:
        counts[metric.reason] = counts.get(metric.reason, 0) + 1
    return max(counts.items(), key=lambda item: item[1])[0]


def _merge_short_segments(
    segments: Sequence[SceneSegment],
    config: SceneGateConfig,
) -> List[SceneSegment]:
    merged: List[SceneSegment] = []

    for segment in segments:
        if (
            merged
            and merged[-1].category == segment.category
            and segment.start_ms - merged[-1].end_ms <= config.merge_gap_ms
        ):
            merged[-1] = _merge_pair(merged[-1], segment)
            continue

        if merged and segment.end_ms - segment.start_ms < config.min_segment_ms:
            merged[-1] = _merge_pair(merged[-1], segment, keep_category=True)
            continue

        merged.append(segment)

    return merged


def _smooth_segments(
    segments: Sequence[SceneSegment],
    config: SceneGateConfig,
    candidate_windows: Sequence[CandidateWindow],
) -> List[SceneSegment]:
    smoothed = _merge_short_segments(segments, config)

    for _ in range(max(1, len(smoothed))):
        changed = False
        next_segments: List[SceneSegment] = []
        for index, segment in enumerate(smoothed):
            duration_ms = segment.end_ms - segment.start_ms
            previous_segment = smoothed[index - 1] if index > 0 else None
            next_segment = smoothed[index + 1] if index + 1 < len(smoothed) else None

            if (
                segment.category == "idle"
                and duration_ms < config.min_idle_ms
                and (
                    (previous_segment is not None and previous_segment.category == "rally")
                    or (next_segment is not None and next_segment.category == "rally")
                )
            ):
                next_segments.append(
                    _relabel_segment(segment, "rally", "short_idle_gap_bridged", 0.5)
                )
                changed = True
                continue

            if (
                segment.category == "rally"
                and duration_ms < config.min_rally_ms
                and not _overlaps_candidate_window(segment, candidate_windows)
            ):
                next_segments.append(
                    _relabel_segment(segment, "idle", "short_rally_blip_suppressed", 0.55)
                )
                changed = True
                continue

            next_segments.append(segment)

        next_segments = _merge_adjacent_same_category(next_segments)
        if not changed and len(next_segments) == len(smoothed):
            return next_segments
        smoothed = next_segments

    return smoothed


def _relabel_segment(
    segment: SceneSegment,
    category: SceneTimelineCategory,
    reason: str,
    confidence: float,
) -> SceneSegment:
    return SceneSegment(
        category=category,
        start_ms=segment.start_ms,
        end_ms=segment.end_ms,
        confidence=confidence,
        reason=reason,
        source_frame_range=segment.source_frame_range,
    )


def _overlaps_candidate_window(
    segment: SceneSegment,
    candidate_windows: Sequence[CandidateWindow],
) -> bool:
    return any(
        window.start_ms < segment.end_ms and window.end_ms > segment.start_ms
        for window in candidate_windows
    )


def _merge_adjacent_same_category(segments: Sequence[SceneSegment]) -> List[SceneSegment]:
    merged: List[SceneSegment] = []
    for segment in segments:
        if merged and merged[-1].category == segment.category:
            merged[-1] = _merge_pair(merged[-1], segment)
        else:
            merged.append(segment)
    return merged


def _merge_pair(
    previous: SceneSegment,
    current: SceneSegment,
    keep_category: bool = False,
) -> SceneSegment:
    previous_duration = max(0.0, previous.end_ms - previous.start_ms)
    current_duration = max(0.0, current.end_ms - current.start_ms)
    total_duration = previous_duration + current_duration
    confidence = (
        (previous.confidence * previous_duration + current.confidence * current_duration)
        / total_duration
        if total_duration > 0
        else max(previous.confidence, current.confidence)
    )
    category = previous.category if keep_category else current.category
    reason = previous.reason if keep_category else current.reason
    if previous.category == current.category and previous.reason != current.reason:
        reason = f"{category}_merged_after_temporal_smoothing"
    return SceneSegment(
        category=category,
        start_ms=previous.start_ms,
        end_ms=current.end_ms,
        confidence=round(confidence, 3),
        reason=reason,
        source_frame_range=[
            previous.source_frame_range[0],
            current.source_frame_range[-1],
        ],
    )


def _merge_candidate_windows(windows: Sequence[CandidateWindow]) -> List[CandidateWindow]:
    if not windows:
        return []

    ordered = sorted(windows, key=lambda item: item.start_ms)
    merged = [ordered[0]]
    for window in ordered[1:]:
        previous = merged[-1]
        if window.start_ms <= previous.end_ms:
            confidence = max(previous.confidence, window.confidence)
            reason = previous.reason if previous.confidence >= window.confidence else window.reason
            peak_frame_id = (
                previous.peak_frame_id
                if previous.confidence >= window.confidence
                else window.peak_frame_id
            )
            merged[-1] = CandidateWindow(
                start_ms=min(previous.start_ms, window.start_ms),
                end_ms=max(previous.end_ms, window.end_ms),
                reason=reason,
                peak_frame_id=peak_frame_id,
                confidence=confidence,
            )
        else:
            merged.append(window)
    return merged


def _clip_candidates_to_rally_segments(
    windows: Sequence[CandidateWindow],
    segments: Sequence[SceneSegment],
    metrics: Sequence[FrameMetric],
    config: SceneGateConfig,
) -> List[SceneCandidate]:
    candidates: List[SceneCandidate] = []
    for segment_index, segment in enumerate(segments):
        if segment.category != "rally":
            continue
        for window in windows:
            start_ms = max(segment.start_ms, window.start_ms)
            end_ms = min(segment.end_ms, window.end_ms)
            if end_ms - start_ms < config.min_candidate_ms:
                continue
            frame_range = _frame_range_for_interval(metrics, start_ms, end_ms)
            candidates.append(
                SceneCandidate(
                    start_ms=round(start_ms, 3),
                    end_ms=round(end_ms, 3),
                    confidence=window.confidence,
                    reason=window.reason,
                    source_frame_range=frame_range,
                    parent_segment_index=segment_index,
                )
            )
    return candidates


def _attach_candidates(
    segments: Sequence[SceneSegment],
    candidates: Sequence[SceneCandidate],
) -> List[SceneSegment]:
    attached: List[SceneSegment] = []
    for index, segment in enumerate(segments):
        segment_candidates = [item for item in candidates if item.parent_segment_index == index]
        attached.append(
            SceneSegment(
                category=segment.category,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                confidence=segment.confidence,
                reason=segment.reason,
                source_frame_range=segment.source_frame_range,
                smash_candidates=segment_candidates,
            )
        )
    return attached


def _frame_range_for_interval(
    metrics: Sequence[FrameMetric],
    start_ms: float,
    end_ms: float,
) -> List[int]:
    interval_metrics = [metric for metric in metrics if start_ms <= metric.time_ms <= end_ms]
    if not interval_metrics:
        nearest = min(metrics, key=lambda item: abs(item.time_ms - start_ms))
        return [nearest.frame_id, nearest.frame_id]
    return [interval_metrics[0].frame_id, interval_metrics[-1].frame_id]


def _category_durations(segments: Sequence[SceneSegment]) -> dict[str, float]:
    durations: dict[str, float] = {}
    for segment in segments:
        durations[segment.category] = durations.get(segment.category, 0.0) + max(
            0.0,
            segment.end_ms - segment.start_ms,
        )
    return durations


def _effective_duration_ms(metrics: Sequence[FrameMetric], video_duration_ms: float) -> float:
    if video_duration_ms > 0:
        return video_duration_ms
    if not metrics:
        return 0.0
    return metrics[-1].time_ms


def _build_roi_mask(shape: Tuple[int, int], config: SceneGateConfig, cv2: object, np: object) -> object:
    if not config.roi_polygon:
        return None

    height, width = shape
    points = []
    for x, y in config.roi_polygon:
        if config.roi_is_relative:
            points.append((int(round(x * width)), int(round(y * height))))
        else:
            points.append((int(round(x)), int(round(y))))

    mask = np.zeros(shape, dtype=np.uint8)
    cv2.fillPoly(mask, [np.array(points, dtype=np.int32)], 255)
    return mask
