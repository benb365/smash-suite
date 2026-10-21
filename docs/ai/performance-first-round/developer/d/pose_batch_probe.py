#!/usr/bin/env python3
"""Small selected real-frame crop probe for the D pose path; prepare only, do not run automatically."""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

import av
import cv2
import numpy as np
import torch


def load_estimator(source: Path, weight: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.PoseEstimator(weight)


def load_frame(video: Path, frame_id: int):
    with av.open(str(video)) as container:
        for fid, frame in enumerate(container.decode(video=0)):
            if fid == frame_id:
                image = frame.to_ndarray(format="bgr24")
                if image.shape[:2] != (1080, 1920):
                    image = cv2.resize(image, (1920, 1080))
                return image
    raise ValueError(f"frame_id {frame_id} is outside the video")


def crop_players(image, sample):
    crops = []
    for player in sample["players"]:
        box = player["box"]
        height = box["y2"] - box["y1"]
        x1 = max(0, int(box["x1"] - .2 * height))
        x2 = min(1920, int(box["x2"] + .2 * height))
        y1 = max(0, int(box["y1"] - .12 * height))
        y2 = min(1080, int(box["y2"] + .12 * height))
        crop = image[y1:y2, x1:x2]
        if crop.size:
            crops.append(dict(player_id=player["player_id"], box_index=player["box_index"],
                              crop=crop, crop_xyxy=[x1, y1, x2, y2]))
    if len(crops) not in (1, 2):
        raise ValueError(f"frame {sample['frame_id']} must have one or two nonempty selected real-frame crops")
    return crops


def arrays(result):
    return {key: np.asarray(value) for key, value in result.items()}


def max_difference(left, right):
    left, right = arrays(left), arrays(right)
    report = {}
    for key in sorted(left.keys() & right.keys()):
        if left[key].shape != right[key].shape:
            report[key] = dict(reference_shape=list(left[key].shape), candidate_shape=list(right[key].shape))
        elif left[key].size:
            report[key] = dict(max_abs=float(np.max(np.abs(left[key] - right[key]))))
        else:
            report[key] = dict(max_abs=0.0)
    return report


def watch_padding(estimator):
    observations = []

    def capture(_module, _inputs, output):
        images = output[0]
        observations.append(dict(
            batch_images=len(images.image_sizes),
            padded_tensor_shape=list(images.tensors.shape),
            resized_image_sizes=[list(size) for size in images.image_sizes]))

    return observations, estimator.model.transform.register_forward_hook(capture)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-source", type=Path, required=True)
    parser.add_argument("--candidate-source", type=Path, required=True)
    parser.add_argument("--weight", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--samples-json", type=Path, required=True,
                        help="Frame IDs and player boxes for selected real-frame crops; at most two players per frame")
    args = parser.parse_args()
    samples = json.loads(args.samples_json.read_text(encoding="utf-8"))
    reference = load_estimator(args.reference_source, args.weight, "pose_reference")
    candidate = load_estimator(args.candidate_source, args.weight, "pose_candidate")
    reference_padding, reference_hook = watch_padding(reference)
    candidate_padding, candidate_hook = watch_padding(candidate)
    report = []
    for sample in samples:
        crops = crop_players(load_frame(args.video, int(sample["frame_id"])), sample)
        # Verify the copy-removal premise on the actual selected real-frame crops.
        copy_checks = []
        for item in crops:
            crop = item["crop"]
            before = crop.copy()
            converted = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            converted_copy = converted.copy()
            tensor_without_copy = torch.from_numpy(converted).permute(2, 0, 1).float() / 255
            tensor_with_copy = torch.from_numpy(converted_copy).permute(2, 0, 1).float() / 255
            copy_checks.append(dict(
                crop_shape=list(crop.shape), converted_shape=list(converted.shape),
                converted_dtype=str(converted.dtype), converted_c_contiguous=bool(converted.flags.c_contiguous),
                converted_owns_data=bool(converted.flags.owndata), shares_crop_memory=bool(np.shares_memory(converted, crop)),
                crop_unchanged=bool(np.array_equal(crop, before)),
                copy_values_equal=bool(np.array_equal(converted, converted_copy)),
                tensor_shapes_equal=bool(tensor_without_copy.shape == tensor_with_copy.shape),
                tensor_values_equal=bool(torch.equal(tensor_without_copy, tensor_with_copy))))
        reference_results = []
        candidate_single_results = []
        reference_shapes = []
        candidate_single_shapes = []
        reference_s = candidate_single_s = 0.0
        for item in crops:
            start = time.perf_counter()
            reference_results.append(reference(item["crop"]))
            reference_s += time.perf_counter() - start
            reference_shapes.append(reference_padding[-1])
            start = time.perf_counter()
            candidate_single_results.append(candidate(item["crop"]))
            candidate_single_s += time.perf_counter() - start
            candidate_single_shapes.append(candidate_padding[-1])
        start = time.perf_counter()
        candidate_batch_results = candidate.predict_batch([item["crop"] for item in crops])
        candidate_batch_s = time.perf_counter() - start
        candidate_batch_shape = candidate_padding[-1]
        report.append(dict(
            frame_id=int(sample["frame_id"]),
            identities=[dict(player_id=item["player_id"], box_index=item["box_index"], crop_xyxy=item["crop_xyxy"])
                        for item in crops],
            copy_checks=copy_checks,
            padding_observations=dict(scope="these sampled calls only", reference_single=reference_shapes,
                                      candidate_single=candidate_single_shapes, candidate_batch=candidate_batch_shape),
            model_calls=dict(reference_single=len(crops), candidate_single=len(crops), candidate_batch=1),
            seconds=dict(reference_single=reference_s, candidate_single=candidate_single_s,
                         candidate_batch=candidate_batch_s),
            reference_vs_candidate_single=[max_difference(a, b) for a, b in zip(reference_results, candidate_single_results)],
            candidate_single_vs_batch=[max_difference(a, b) for a, b in zip(candidate_single_results, candidate_batch_results)]))
    reference_hook.remove()
    candidate_hook.remove()
    print(json.dumps(dict(samples=report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
