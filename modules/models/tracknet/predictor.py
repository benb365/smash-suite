from __future__ import annotations
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ShuttlePoint:
    x: float
    y: float
    confidence: float

def heatmap_candidates(heatmap, *, width, height):
    """Record alternative observations, without changing the original decoder.

    Keep small low-confidence peaks for offline association experiments. Each
    score belongs to its own region; no position is inferred across frames.
    """
    import cv2
    import numpy as np

    py, px = np.unravel_index(heatmap.argmax(), heatmap.shape)
    def point(x, y, confidence):
        return dict(x=float(x*width/heatmap.shape[1]), y=float(y*height/heatmap.shape[0]),
                    confidence=float(confidence))
    peak = point(px, py, heatmap[py, px])
    threshold = (heatmap > .6).astype(np.uint8)
    contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = peak
    if contours:
        contour = max(contours, key=lambda c: cv2.boundingRect(c)[2]*cv2.boundingRect(c)[3])
        bx, by, bw, bh = cv2.boundingRect(contour)
        _, labels = cv2.connectedComponents(threshold)
        x, y = contour[0, 0]
        largest = point(bx+bw/2, by+bh/2, heatmap[labels == labels[y, x]].max())
    maxima = ((heatmap == cv2.dilate(heatmap, np.ones((5, 5), np.uint8)))
              & (heatmap >= .1)).astype(np.uint8)
    regions, _ = cv2.findContours(maxima, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    peaks = []
    for region in regions:
        x, y = region[0, 0]
        peaks.append(point(x, y, heatmap[y, x]))
    peaks.sort(key=lambda p: p['confidence'], reverse=True)
    return dict(global_peak=peak, largest_region=largest, peaks=peaks[:32],
                peak_floor=.1, max_peaks=32)


def _fold_grayscale_first_layer(model):
    import torch

    conv = model.conv2d_1.conv
    if conv.in_channels != 9 or conv.groups != 1:
        raise ValueError("Grayscale TrackNet requires an ungrouped 9-channel first layer")
    old_weight = conv.weight
    folded = old_weight.detach().reshape(conv.out_channels, 3, 3, *old_weight.shape[-2:]).sum(dim=2)
    conv.weight = torch.nn.Parameter(folded, requires_grad=old_weight.requires_grad)
    conv.in_channels = 3


class TrackNetPredictor:
    """TrackNet inference and the recorded point/candidate decoder."""
    def __init__(self, weight=None, *, device="cpu", record_candidates=False, statistics=None,
                 small_input=False, grayscale=False):
        import torch
        from .model import TrackNet
        from modules.models.assets import ensure_models
        if weight is None:
            weight = ensure_models(["ball_track.pt"])["ball_track.pt"]
        self.torch, self.device = torch, device
        self.record_candidates = record_candidates
        self.statistics = statistics
        self.small_input = bool(small_input)
        self.grayscale = bool(grayscale)
        self.input_size = (288, 512)
        self.content_size = (288, 512)
        self.color_mode = "gray" if self.grayscale else "rgb"
        self.last_candidates = []
        self._preprocessed_cache = OrderedDict()
        self._cache_peak_items = 0
        torch.set_num_threads(4)
        self.model = TrackNet()
        self.model.load_state_dict(torch.load(weight, map_location="cpu", weights_only=True))
        if self.grayscale:
            _fold_grayscale_first_layer(self.model)
        self.model.eval().to(device)

    def __call__(self, frames: list[Any], *, frame_ids: list[int] | None = None) -> list[ShuttlePoint]:
        import cv2
        import numpy as np
        from torchvision.transforms.functional import resize

        started = time.perf_counter()
        if frame_ids is not None and len(frame_ids) != len(frames):
            raise ValueError("frame_ids must match frames")
        use_cache = frame_ids is not None
        tensors = []
        content_sizes = []
        for index, frame in enumerate(frames):
            frame_id = frame_ids[index] if use_cache else None
            if use_cache and frame_id in self._preprocessed_cache:
                tensor = self._preprocessed_cache.pop(frame_id)
                self._preprocessed_cache[frame_id] = tensor
                if self.statistics is not None:
                    self.statistics.add("tracknet_cache_hits")
                content_size = self._content_dimensions(frame)
            else:
                if self.grayscale:
                    image = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    tensor = self.torch.from_numpy(image).unsqueeze(0).float().div_(255)
                else:
                    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    tensor = self.torch.from_numpy(image).permute(2, 0, 1).float().div_(255)
                content_size = self._content_dimensions(frame)
                if self.small_input:
                    height, width = content_size
                    tensor = resize(tensor, [height, width], antialias=True)
                    padded_height = (height + 7) // 8 * 8
                    padded_width = (width + 7) // 8 * 8
                    tensor = self.torch.nn.functional.pad(
                        tensor, (0, padded_width - width, 0, padded_height - height))
                else:
                    tensor = resize(tensor, [288, 512], antialias=True)
                    content_size = (288, 512)
                if use_cache:
                    self._preprocessed_cache[frame_id] = tensor
                    if len(self._preprocessed_cache) > 3:
                        self._preprocessed_cache.popitem(last=False)
                    self._cache_peak_items = max(self._cache_peak_items, len(self._preprocessed_cache))
                    if self.statistics is not None:
                        self.statistics.add("tracknet_cache_misses")
                        self.statistics.add("tracknet_cache_prepared_frames")
            tensors.append(tensor)
            content_sizes.append(content_size)
        self.input_size = tuple(tensors[0].shape[-2:])
        self.content_size = content_sizes[0]
        preprocessed = time.perf_counter()
        with self.torch.inference_mode():
            heatmaps = self.model(self.torch.cat(tensors).unsqueeze(0).to(self.device))[0].cpu().numpy()
        inferred = time.perf_counter()
        points = []
        self.last_candidates = []
        for frame, heatmap, content_size in zip(frames, heatmaps, content_sizes):
            content_height, content_width = content_size
            heatmap = heatmap[:content_height, :content_width]
            if self.record_candidates:
                self.last_candidates.append(heatmap_candidates(
                    heatmap, width=frame.shape[1], height=frame.shape[0]))
            py, px = np.unravel_index(heatmap.argmax(), heatmap.shape)
            x, y = float(px), float(py)
            contours, _ = cv2.findContours((heatmap > 0.6).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                bx, by, bw, bh = max((cv2.boundingRect(contour) for contour in contours), key=lambda box: box[2] * box[3])
                x, y = bx + bw / 2, by + bh / 2
            points.append(ShuttlePoint(x * frame.shape[1] / heatmap.shape[1],
                                       y * frame.shape[0] / heatmap.shape[0], float(heatmap[py, px])))
        self.last_timing = dict(preprocess_s=preprocessed - started,
                                inference_and_transfer_s=inferred - preprocessed,
                                point_decode_s=time.perf_counter() - inferred)
        if self.statistics is not None:
            self.statistics.add("tracknet_calls")
            self.statistics.add("tracknet_input_frames", len(frames))
            self.statistics.add("candidate_peaks", sum(len(row["peaks"]) for row in self.last_candidates))
            for name, seconds in self.last_timing.items():
                self.statistics.timing("tracknet_" + name, seconds)
        return points

    def clear_preprocessed_cache(self):
        if self.statistics is not None:
            self.statistics.add("tracknet_cache_max_items", self._cache_peak_items)
        self._preprocessed_cache.clear()

    def _content_dimensions(self, frame):
        height, width = frame.shape[:2]
        if not self.small_input:
            return 288, 512
        scale = min(1.0, 320.0 / max(height, width))
        return max(1, round(height * scale)), max(1, round(width * scale))
