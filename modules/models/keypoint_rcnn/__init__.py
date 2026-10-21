"""Keypoint R-CNN inference on a person crop or image."""
class PoseEstimator:
    def __init__(self, weight=None):
        import torch
        import torchvision  # Registers classes in the pinned upstream checkpoint.
        from modules.models.assets import ensure_models
        if weight is None:
            weight = ensure_models(["pose_kpRCNN.pth"])["pose_kpRCNN.pth"]
        self.torch = torch
        self.model = torch.load(weight, map_location="cpu", weights_only=False).eval()
        self.model.transform.min_size, self.model.transform.max_size = (192,), 384
        self.model.roi_heads.detections_per_img = 3
        self.model.rpn._pre_nms_top_n["testing"], self.model.rpn._post_nms_top_n["testing"] = 200, 200

    def _prepare(self, image, statistics=None):
        import cv2
        import time
        enabled = statistics is not None and statistics.enabled
        tick = time.monotonic() if enabled else None
        tensor = self.torch.from_numpy(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float() / 255
        if enabled:
            statistics.timing("pose_input_preparation_s", time.monotonic() - tick)
        return tensor

    def _convert(self, output, statistics=None):
        import time
        enabled = statistics is not None and statistics.enabled
        tick = time.monotonic() if enabled else None
        result = {k: v.cpu().numpy() for k, v in output.items()}
        if enabled:
            statistics.timing("pose_result_conversion_s", time.monotonic() - tick)
        return result

    def __call__(self, image, statistics=None):
        tensor = self._prepare(image, statistics)
        import time
        enabled = statistics is not None and statistics.enabled
        tick = time.monotonic() if enabled else None
        with self.torch.inference_mode():
            output = self.model([tensor])[0]
        if enabled:
            statistics.timing("pose_model_call_s", time.monotonic() - tick)
        return self._convert(output, statistics)
