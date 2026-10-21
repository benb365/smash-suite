from __future__ import annotations
import time
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

class TrackNetPredictor:
    """TrackNet inference and the recorded point/candidate decoder."""
    def __init__(self, weight=None, *, device="cpu", record_candidates=False, statistics=None):
        import torch
        from .model import TrackNet
        from modules.models.assets import ensure_models
        if weight is None:
            weight = ensure_models(["ball_track.pt"])["ball_track.pt"]
        self.torch, self.device = torch, device
        self.record_candidates = record_candidates
        self.statistics = statistics
        self.last_candidates = []
        torch.set_num_threads(4)
        self.model = TrackNet()
        self.model.load_state_dict(torch.load(weight, map_location="cpu", weights_only=True))
        self.model.eval().to(device)

    def __call__(self, frames: list[Any]) -> list[ShuttlePoint]:
        import cv2
        import numpy as np
        from torchvision.transforms.functional import resize

        started = time.perf_counter()
        tensors = []
        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            tensor = self.torch.from_numpy(rgb.copy()).permute(2, 0, 1).float() / 255
            tensors.append(resize(tensor, [288, 512], antialias=True))
        preprocessed = time.perf_counter()
        with self.torch.inference_mode():
            heatmaps = self.model(self.torch.cat(tensors).unsqueeze(0).to(self.device))[0].cpu().numpy()
        inferred = time.perf_counter()
        points = []
        self.last_candidates = []
        for frame, heatmap in zip(frames, heatmaps):
            if self.record_candidates:
                self.last_candidates.append(heatmap_candidates(
                    heatmap, width=frame.shape[1], height=frame.shape[0]))
            py, px = np.unravel_index(heatmap.argmax(), heatmap.shape)
            x, y = float(px), float(py)
            contours, _ = cv2.findContours((heatmap > 0.6).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                bx, by, bw, bh = max((cv2.boundingRect(contour) for contour in contours), key=lambda box: box[2] * box[3])
                x, y = bx + bw / 2, by + bh / 2
            points.append(ShuttlePoint(x * frame.shape[1] / 512, y * frame.shape[0] / 288, float(heatmap[py, px])))
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
