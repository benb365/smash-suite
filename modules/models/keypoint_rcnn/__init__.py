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

    def __call__(self, image):
        import cv2
        tensor = self.torch.from_numpy(cv2.cvtColor(image, cv2.COLOR_BGR2RGB).copy()).permute(2, 0, 1).float() / 255
        with self.torch.inference_mode():
            return {k: v.cpu().numpy() for k, v in self.model([tensor])[0].items()}
