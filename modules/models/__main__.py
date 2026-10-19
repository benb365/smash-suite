"""Run one model on actual timestamped video frames, without rally segmentation."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path
from modules.media.video_input import FileFrameSource


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("tracknet", "yolo11n", "keypoint_rcnn"), required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit-s", type=float, default=None)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.model == "tracknet":
        from .tracknet import TrackNetPredictor
        model = TrackNetPredictor(device=args.device, record_candidates=True)
    elif args.model == "yolo11n":
        from .yolo11n import PersonDetector
        model = PersonDetector(device=args.device)
    else:
        from .keypoint_rcnn import PoseEstimator
        model = PoseEstimator()  # The recorded pose checkpoint runs on CPU.
    pending = []
    with FileFrameSource(args.video, limit_s=args.limit_s) as frames, args.output.open("w") as output:
        for frame in frames:
            if args.model == "tracknet":
                pending.append(frame)
                if len(pending) < 3:
                    continue
                points = model([f.image for f in pending])
                rows = [dict(frame_id=f.frame_id, timestamp_ms=f.timestamp_ms,
                             point=asdict(p), candidates=c) for f, p, c in zip(pending, points, model.last_candidates)]
                pending.clear()
            else:
                result = model([frame.image])[0] if args.model == "yolo11n" else {k:v.tolist() for k,v in model(frame.image).items()}
                rows = [dict(frame_id=frame.frame_id, timestamp_ms=frame.timestamp_ms, result=result)]
            for row in rows:
                output.write(json.dumps(row, ensure_ascii=False)+"\n")
    if pending:
        print(f"TrackNet: {len(pending)} trailing frames do not form a three-frame group.")


if __name__ == "__main__":
    main()
