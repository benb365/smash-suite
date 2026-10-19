"""YOLO11n person detection; output boxes use source-image coordinates."""
class PersonDetector:
    def __init__(self, weight=None, *, device="cpu"):
        from ultralytics import YOLO
        from modules.models.assets import ensure_models
        if weight is None:
            weight = ensure_models(["yolo11n.pt"])["yolo11n.pt"]
        self.model, self.device = YOLO(str(weight)), device

    def __call__(self, images, *, confidence=.2, image_size=960):
        outputs = self.model.predict(images, classes=[0], conf=confidence, imgsz=image_size,
                                     device=self.device, verbose=False)
        return [[dict(x1=float(b[0]), y1=float(b[1]), x2=float(b[2]), y2=float(b[3]), confidence=float(c))
                 for b, c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy())] for r in outputs]
