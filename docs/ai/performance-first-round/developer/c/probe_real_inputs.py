"""Main-controller probe for real TrackNet frames; intentionally not run by developer C."""
from __future__ import annotations

import argparse
import hashlib
import json
import resource
from pathlib import Path

import cv2
import numpy as np
import torch
from torchvision.transforms.functional import resize

from modules.models.tracknet import TrackNetPredictor
from modules.models.tracknet.predictor import heatmap_candidates
from modules.rally.statistics import Statistics
from modules.rally.recognize import normalized
from modules.media.video_input import FileFrameSource


WINDOWS = ((0, 1, 2), (1, 2, 3), (3, 4, 5), (4, 5, 6))


class RecordingModel:
    def __init__(self, model):
        self.model = model
        self.batches = []
        self.heatmaps = []

    def __call__(self, batch):
        self.batches.append(batch[0].detach().cpu().clone())
        output = self.model(batch)
        self.heatmaps.append(output[0].detach().cpu().clone())
        return output


def tensor_for(frame, *, copy_rgb):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    source = rgb.copy() if copy_rgb else rgb
    tensor = torch.from_numpy(source).permute(2, 0, 1).float() / 255
    return resize(tensor, [288, 512], antialias=True), rgb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weight", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--reference-source", required=True, type=Path)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if not args.weight.is_file() or not args.video.is_file() or not args.reference_source.is_file():
        raise SystemExit("weight, video, and reference source must exist")

    frames = []
    with FileFrameSource(args.video, mode="offline") as source:
        for frame in source:
            frames.append(normalized(frame))
            if len(frames) == 7:
                break
    if len(frames) < 7:
        raise SystemExit(f"need at least 7 decoded frames, got {len(frames)}")

    reference_hash = hashlib.sha256(args.reference_source.read_bytes()).hexdigest()
    maxrss_before_model = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    predictor = TrackNetPredictor(args.weight, device=args.device, record_candidates=True,
                                  statistics=Statistics(enabled=True))
    maxrss_after_model_init = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    recorder = RecordingModel(predictor.model)
    predictor.model = recorder
    reference_tensors = []
    ownership = []
    for frame in frames:
        tensor_with_copy, rgb = tensor_for(frame.image, copy_rgb=True)
        tensor_without_copy, rgb_again = tensor_for(frame.image, copy_rgb=False)
        reference_tensors.append(tensor_with_copy)
        ownership.append({
            "rgb_owns_data": bool(rgb_again.flags.owndata),
            "rgb_c_contiguous": bool(rgb_again.flags.c_contiguous),
            "rgb_shares_with_source": bool(np.shares_memory(rgb_again, frame.image)),
            "rgb_equal_to_copy_result": bool(np.array_equal(rgb, rgb_again)),
            "tensor_strict_equal": bool(torch.equal(tensor_with_copy, tensor_without_copy)),
        })

    current_candidates = []
    for window in WINDOWS:
        predictor([frames[i].image for i in window], frame_ids=list(window))
        current_candidates.append(predictor.last_candidates)

    tensor_matches = []
    tensor_shapes = []
    heatmap_matches = []
    candidate_matches = []
    for index, window in enumerate(WINDOWS):
        reference_batch = torch.cat([reference_tensors[i] for i in window]).unsqueeze(0).to(args.device)
        current_batch = recorder.batches[index]
        reference_tensor_batch = reference_batch[0].cpu()
        tensor_shapes.append({
            "current": list(current_batch.shape),
            "reference": list(reference_tensor_batch.shape),
        })
        tensor_matches.append(bool(torch.equal(current_batch, reference_tensor_batch)))
        with torch.inference_mode():
            reference_heatmaps = predictor.model.model(reference_batch)[0].cpu()
        actual_heatmaps = recorder.heatmaps[index]
        heatmap_matches.append(bool(torch.equal(actual_heatmaps, reference_heatmaps)))
        ref_candidates = [heatmap_candidates(h.numpy(), width=frames[fid].image.shape[1],
                                              height=frames[fid].image.shape[0])
                          for fid, h in zip(window, reference_heatmaps)]
        candidate_matches.append(ref_candidates == current_candidates[index])

    live_cache_bytes = sum(tensor.numel() * tensor.element_size()
                           for tensor in predictor._preprocessed_cache.values())
    maxrss_after_windows = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    predictor.clear_preprocessed_cache()
    print(json.dumps({
        "reference_source_sha256": reference_hash,
        "windows_frame_ids": WINDOWS,
        "tensor_matches": tensor_matches,
        "tensor_shapes": tensor_shapes,
        "model_heatmap_matches": heatmap_matches,
        "candidate_matches": candidate_matches,
        "rgb_ownership_and_tensor_checks": ownership,
        "prepared_frames": predictor.statistics.counts.get("tracknet_cache_prepared_frames", 0),
        "cache_peak_items": predictor._cache_peak_items,
        "cache_tensor_bytes_at_peak": 3 * 3 * 288 * 512 * 4,
        "cache_tensor_bytes_before_release": live_cache_bytes,
        "process_maxrss_before_model": maxrss_before_model,
        "process_maxrss_after_model_init": maxrss_after_model_init,
        "process_maxrss_after_windows": maxrss_after_windows,
        "process_maxrss_unit": "bytes on macOS; KiB on Linux",
        "decoded_frames": len(frames),
        "model_input_frames": sum(len(window) for window in WINDOWS),
        "cache_items_after_release": len(predictor._preprocessed_cache),
    }, indent=2))
    if not all(tensor_matches + heatmap_matches + candidate_matches):
        raise SystemExit("strict equivalence check failed")
    if not all(row["rgb_owns_data"] and row["rgb_c_contiguous"] and
               not row["rgb_shares_with_source"] and row["tensor_strict_equal"] for row in ownership):
        raise SystemExit("RGB copy assumptions failed")


if __name__ == "__main__":
    main()
