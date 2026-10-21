"""Keypoint R-CNN inference on a person crop or image."""
from time import perf_counter


class PoseEstimator:
    def __init__(self, weight=None, *, device="cpu"):
        started = perf_counter()
        import torch
        import torchvision  # Registers classes in the pinned upstream checkpoint.
        from modules.models.assets import ensure_models
        selected = torch.device(device)
        if selected.type not in ("cpu", "cuda"):
            raise ValueError("PoseEstimator device must be cpu or cuda.")
        if selected.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested for PoseEstimator but is unavailable.")
        if weight is None:
            weight = ensure_models(["pose_kpRCNN.pth"])["pose_kpRCNN.pth"]
        self.torch = torch
        self.device = str(selected)
        self.model = torch.load(weight, map_location="cpu", weights_only=False).eval()
        self.model.transform.min_size, self.model.transform.max_size = (192,), 384
        self.model.roi_heads.detections_per_img = 3
        self.model.rpn._pre_nms_top_n["testing"], self.model.rpn._post_nms_top_n["testing"] = 200, 200
        self.model.to(device=self.device, dtype=torch.float32)
        self._timings = dict(initialization_s=perf_counter() - started,
                             tensor_preparation_s=0.0, inference_and_transfer_s=0.0,
                             batch_count=0, crop_count=0)

    @property
    def timings(self):
        """Return a snapshot of cumulative wall times and successful input counts."""
        return self._timings.copy()

    def __call__(self, image):
        return self.predict_batch([image])[0]

    def predict_batch(self, images):
        """Infer one ordered batch of BGR images; return NumPy dictionaries."""
        import cv2
        images = list(images)
        if not images:
            return []
        started = perf_counter()
        tensors = []
        for image in images:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            tensor = self.torch.from_numpy(rgb.copy()).permute(2, 0, 1).float() / 255
            tensors.append(tensor.to(self.device))
        prepared = perf_counter()
        with self.torch.inference_mode():
            predictions = self.model(tensors)
            if len(predictions) != len(images):
                raise RuntimeError("PoseEstimator must return one result for each input image.")
            outputs = [{key: value.cpu().numpy() for key, value in row.items()}
                       for row in predictions]
        # Fetching the actual outputs waits for their device computation; avoid
        # an extra global CUDA synchronization or resetting process-wide stats.
        finished = perf_counter()
        self._timings["tensor_preparation_s"] += prepared - started
        self._timings["inference_and_transfer_s"] += finished - prepared
        self._timings["batch_count"] += 1
        self._timings["crop_count"] += len(images)
        return outputs
