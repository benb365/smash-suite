"""Run the frozen three camera-specific candidates on an arbitrary local MP4.

This is a file-processing product. The C/D candidates use future context and
must not be represented as implementations of the causal RallyStream contract.
"""
from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np

from app.product_types import ProcessRequest, VideoInfo
from app.vision.rally_stream import RallyStream, TimestampedFrame
from app.vision.tracknet_rally import TrackNetPredictor
from app.vision.trajectory_rally import TrajectoryConfig, TrajectoryRallySegmenter
from app.vision.video_input import FileFrameSource


class ProductPredictor(TrackNetPredictor):
    """Reuse the verified preprocessing/decoder with a packaged architecture."""
    def __init__(self, weight: Path, device: str, record_candidates: bool):
        import torch
        from app.algorithms.tracknet_model import TrackNet
        self.torch, self.device = torch, device
        self.record_candidates = record_candidates
        self.last_candidates = []
        torch.set_num_threads(4)
        self.model = TrackNet()
        self.model.load_state_dict(torch.load(weight, map_location="cpu", weights_only=True))
        self.model.eval().to(device)


def normalized(frame):
    # All selected coordinate rules use the recorded 1920x1080 reference.
    # Only inference images are scaled; source PTS and exported pixels are not.
    if frame.image.shape[:2] == (1080, 1920):
        return frame
    return TimestampedFrame(frame.frame_id, frame.timestamp_ms, cv2.resize(frame.image, (1920, 1080)))


def recognize(source: Path, info: VideoInfo, options: ProcessRequest, weights: dict, progress, directory: Path):
    import torch
    cv2.setNumThreads(1)
    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    started = time.monotonic()
    predictor = ProductPredictor(weights["ball_track.pt"], device, options.camera_type != "high")
    profile_path = Path(__file__).with_name("algorithms") / "profiles.json"
    profiles = json.loads(profile_path.read_text())
    warnings = []
    if (info.width, info.height) != (1920, 1080):
        warnings.append("识别按 1080p 参考画面计算，成片保持原尺寸；该尺寸的识别效果仍需检查。")
    progress("正在读取录像", .01)
    if options.camera_type == "high":
        predictions = []
        config = TrajectoryConfig(**profiles["high"])
        segmenter = TrajectoryRallySegmenter(predictor, width=1920, height=1080, config=config)
        stream = RallyStream(segmenter)
        last = time.monotonic()
        with FileFrameSource(source, mode="offline") as frames:
            for frame in frames:
                predictions.extend(asdict(p) for p in stream.process(normalized(frame)))
                if time.monotonic() - last > 1:
                    progress("正在识别对打回合", min(.95, frame.timestamp_ms / info.duration_ms))
                    last = time.monotonic()
        if segmenter.active or segmenter.start_ms is not None:
            warnings.append("片尾存在未确认结束的候选对打，未将其伪造成完整回合。")
        if segmenter.pending:
            warnings.append(f"片尾剩余 {len(segmenter.pending)} 帧不足一个模型输入组，未补造帧。")
        diagnostics = dict(algorithm="high-trajectory-frozen-20261018", config=profiles["high"],
                           decoded_frames=frames.stats["frames_delivered"])
    else:
        observations = observe(source, info, options, predictor, weights["yolo11n.pt"], device, progress)
        native, shifted, features = observations
        if len(native) < 3 or len(features) < 2:
            raise ValueError("录像太短，缺少足够的真实帧和人物观测，无法识别回合。")
        if options.camera_type == "courtside":
            from app.algorithms import player_paths as players
            from app.algorithms.court_pipeline import pipeline
            from app.algorithms.shuttle_paths import observed_candidates, associate
            from app.algorithms.coherent_flights import split, moving_points, fit, contact_points
            if options.court:
                players.COURT = np.array([[x * 1920, y * 1080] for x, y in options.court], np.float32)
            seeds = players.main_players(features[0]["boxes"])
            if len(seeds) != 2:
                raise ValueError("首帧未能选出主球场的两名球员。请圈选主球场，或换用开头有两名球员的录像。")
            floor = min(b["y2"] - .5 * players.height(b) for b in seeds)
            rows, maps = [], []
            for row in features:
                ids = [i for i, b in enumerate(row["boxes"]) if b["y2"] >= floor]
                maps.append(ids)
                rows.append(dict(row, boxes=[row["boxes"][i] for i in ids], features=[row["features"][i] for i in ids]))
            people = players.tracks(rows, "appearance")
            for row, ids in zip(people, maps):
                for person in row["players"]:
                    person["box_index"] = ids[person["box_index"]]
            progress("正在连接飞行轨迹与人物观测", .66)
            paths = associate(observed_candidates(native, shifted[:len(native)]), "quadratic", 300)
            flights = []
            for track in paths:
                for part in split(track["points"]):
                    moving = moving_points(part)
                    if moving:
                        flights.append(dict(flight_id=len(flights), parent_track_id=track["track_id"], points=part,
                                            moving=moving, fit=fit(part), contacts=contact_points(moving, people)))
            predicted, trace = pipeline(native, shifted, people, flights)
            predictions = [asdict(p) for p in predicted]
            diagnostics = dict(algorithm="courtside-frozen-20261018", selected_people=seeds,
                               native_frames=len(native), shifted_frames=len(shifted))
        else:
            from app.algorithms.players_v2 import track_all, select, follow
            from app.algorithms.refined_person import predict
            from app.vision.candidate_rally import CandidateRallyConfig, candidate_motion
            progress("正在选择并跟踪两名主要球员", .5)
            states = track_all(features)
            try:
                seeds, _ = select(states, features)
            except AssertionError as exc:
                raise ValueError("未能稳定识别两名主要球员，请确认使用单打固定机位录像，或圈选主球场后重试。") from exc
            people = follow(features, seeds)
            ball = candidate_motion(native, width=1920, config=CandidateRallyConfig(**profiles["personal_ball"]))
            signals = person_signals(source, info, people, ball, weights["pose_kpRCNN.pth"], progress)
            if len(signals["times"]) < 2:
                raise ValueError("有效人物观测不足，无法判断连续对打。")
            np.savez_compressed(directory / "person-signals.npz", **signals)
            predicted, trace = predict(signals, info.duration_ms,
                                       dict(ball_only_high=True, min_ball_events=2, min_high_events=1))
            predictions = [asdict(p) for p in predicted]
            diagnostics = dict(algorithm="personal-event-and-group-checks-20261018", native_frames=len(native),
                               person_observations=len(features), selected_track_ids=[s["track_id"] for s in seeds])
        (directory / "decisions.json").write_text(json.dumps(trace), encoding="utf-8")
    if any(not (0 <= p["start_ms"] < p["end_ms"] <= info.duration_ms) for p in predictions):
        raise RuntimeError("识别结果超出视频时间范围，已停止导出。")
    progress("回合识别完成", 1)
    return predictions, dict(warnings=warnings, recognition=diagnostics, device=device,
                             recognition_wall_s=time.monotonic() - started)


def observe(source, info, options, predictor, yolo_weight, device, progress):
    from ultralytics import YOLO
    from app.algorithms.player_paths import descriptor
    from app.algorithms.body_features import body_motion
    detector = YOLO(str(yolo_weight))
    native, shifted, features = {}, {}, []
    queue = deque(maxlen=3)
    person_batch = []
    previous_gray, previous_time = None, None
    last = time.monotonic()
    court = np.array([[x * 1920, y * 1080] for x, y in options.court], np.float32) if options.court else None

    def people_flush():
        nonlocal previous_gray, previous_time
        if not person_batch:
            return
        outputs = detector.predict([f.image for f in person_batch], classes=[0], conf=.2, imgsz=960,
                                   device=device, verbose=False)
        for frame, result in zip(person_batch, outputs):
            boxes = [dict(x1=float(b[0]), y1=float(b[1]), x2=float(b[2]), y2=float(b[3]), confidence=float(c))
                     for b, c in zip(result.boxes.xyxy.cpu().numpy(), result.boxes.conf.cpu().numpy())]
            if court is not None and options.camera_type == "personal":
                boxes = [b for b in boxes if cv2.pointPolygonTest(court, ((b["x1"] + b["x2"]) / 2, b["y2"]), False) >= 0]
            row = dict(frame_id=frame.frame_id, timestamp_ms=frame.timestamp_ms, boxes=boxes)
            descriptors = [descriptor(frame.image, b) for b in boxes]
            if options.camera_type == "personal":
                gray = cv2.cvtColor(cv2.resize(frame.image, (960, 540)), cv2.COLOR_BGR2GRAY)
                dt = (frame.timestamp_ms - previous_time) / 1000 if previous_time is not None else None
                flow = None if previous_gray is None else cv2.calcOpticalFlowFarneback(previous_gray, gray, None, .5, 4, 21, 3, 7, 1.5, 0)
                row.update(appearance=descriptors, body_motion=[None if flow is None else body_motion(flow, b, dt) for b in boxes])
                previous_gray, previous_time = gray, frame.timestamp_ms
            else:
                row["features"] = descriptors
            features.append(row)
        person_batch.clear()

    with FileFrameSource(source, mode="offline") as frames:
        for original in frames:
            frame = normalized(original)
            queue.append(frame)
            if frame.frame_id % 6 == 0:
                person_batch.append(frame)
                if len(person_batch) == 4:
                    people_flush()
            if len(queue) == 3:
                phase = queue[0].frame_id % 3
                if phase == 0 or (phase == 1 and options.camera_type == "courtside"):
                    predictor([f.image for f in queue])
                    target = native if phase == 0 else shifted
                    for f, row in zip(queue, predictor.last_candidates):
                        target[f.frame_id] = dict(row, frame_id=f.frame_id, timestamp_ms=f.timestamp_ms)
                    if phase == 0 and len(native) == 3:
                        shifted[0] = native[0]
            if time.monotonic() - last > 1:
                progress("正在寻找羽毛球和球员", .48 * min(1, frame.timestamp_ms / info.duration_ms))
                last = time.monotonic()
        people_flush()
    if options.camera_type == "courtside" and shifted:
        tail = None
        for fid in range(max(shifted) + 1, frames.stats["frames_delivered"]):
            if fid in native:
                shifted[fid] = native[fid]
            else:
                if tail is None:
                    predictor([f.image for f in queue]); tail = list(predictor.last_candidates)
                j = next(i for i, f in enumerate(queue) if f.frame_id == fid)
                f = list(queue)[j]
                shifted[fid] = dict(tail[j], frame_id=fid, timestamp_ms=f.timestamp_ms)
    return [native[k] for k in sorted(native)], [shifted[k] for k in sorted(shifted)], features


def person_signals(source, info, people, ball, weight, progress):
    import av
    import torch
    import torchvision  # Registers the classes used by the pinned checkpoint.
    from app.algorithms.pose_context import extract
    from app.algorithms.player_paths import height
    model = torch.load(weight, map_location="cpu", weights_only=False).eval()
    model.transform.min_size, model.transform.max_size = (192,), 384
    model.roi_heads.detections_per_img = 3
    model.rpn._pre_nms_top_n["testing"], model.rpn._post_nms_top_n["testing"] = 200, 200
    anchors = {r["frame_id"]: r for r in people}
    rows, arms, highs, counts = [], [], [], []
    pending = None
    last = time.monotonic()
    with av.open(str(source)) as container:
        for fid, frame in enumerate(container.decode(video=0)):
            if fid in anchors:
                image = frame.to_ndarray(format="bgr24")
                if image.shape[:2] != (1080, 1920):
                    image = cv2.resize(image, (1920, 1080))
                row = anchors[fid]
                persons = []
                for person in row["players"]:
                    b = person["box"]; h = height(b)
                    x1, x2 = max(0, int(b["x1"] - .2 * h)), min(1920, int(b["x2"] + .2 * h))
                    y1, y2 = max(0, int(b["y1"] - .12 * h)), min(1080, int(b["y2"] + .12 * h))
                    crop = image[y1:y2, x1:x2]
                    if not crop.size:
                        continue
                    tensor = torch.from_numpy(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).copy()).permute(2, 0, 1).float() / 255
                    with torch.inference_mode():
                        raw = {k: v.cpu().numpy() for k, v in model([tensor])[0].items()}
                    target = np.array([b["x1"] - x1, b["y1"] - y1, b["x2"] - x1, b["y2"] - y1])
                    scores = []
                    for box in raw["boxes"]:
                        area = np.maximum(0, np.minimum(box[2:], target[2:]) - np.maximum(box[:2], target[:2])).prod()
                        union = (box[2:] - box[:2]).prod() + (target[2:] - target[:2]).prod() - area
                        scores.append(float(area / union))
                    best = int(np.argmax(scores)) if scores else None
                    selected = None
                    if best is not None and scores[best] >= .3:
                        points = np.array(raw["keypoints"][best], dtype=np.float64); points[:, 0] += x1; points[:, 1] += y1
                        selected = dict(keypoints=points.tolist(), joint_scores=raw["keypoints_scores"][best].tolist())
                    persons.append(dict(player_id=person["player_id"], box_index=person["box_index"], box=b, selected=selected))
                result = dict(frame_id=fid, timestamp_ms=row["timestamp_ms"], people=persons)
                rows.append(result); arms.append([0., 0.]); highs.append([0., 0.]); counts.append([0., 0.])
                pending = dict(index=len(rows) - 1, row=result, gray=cv2.cvtColor(cv2.resize(image, (960, 540)), cv2.COLOR_BGR2GRAY),
                               pts=float(frame.pts * frame.time_base), values={p["player_id"]: [] for p in persons})
            elif pending and fid - pending["row"]["frame_id"] in (1, 3, 5):
                gray = cv2.cvtColor(cv2.resize(frame.to_ndarray(format="bgr24"), (960, 540)), cv2.COLOR_BGR2GRAY)
                dt = float(frame.pts * frame.time_base) - pending["pts"]
                for person in pending["row"]["people"]:
                    if person["selected"] is None:
                        continue
                    key = person["player_id"]; q = person["selected"]
                    xy = np.array(q["keypoints"])[:, :2]; ids = [5, 6, 9, 10]
                    pts = (xy[ids] / 2).astype(np.float32).reshape(-1, 1, 2); h = height(person["box"])
                    nxt, st, err = cv2.calcOpticalFlowPyrLK(pending["gray"], gray, pts, None, winSize=(15, 15), maxLevel=3,
                                                          criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, .01))
                    if nxt is None:
                        continue
                    back, bst, _ = cv2.calcOpticalFlowPyrLK(gray, pending["gray"], nxt, None, winSize=(15, 15), maxLevel=3,
                                                          criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, .01))
                    if back is None:
                        continue
                    fb = np.linalg.norm((back - pts).reshape(-1, 2) * 2, axis=1) / h
                    conf = np.array(q["joint_scores"])[ids]
                    good = (st.ravel() > 0) & (bst.ravel() > 0) & (fb < .025) & (conf >= 4) & np.isfinite(fb) & (err.ravel() < 35)
                    delta = (nxt - pts).reshape(-1, 2) * 2; hips = (xy[11] + xy[12]) / 2
                    values, raised = [], []
                    for sh, wr in ((0, 2), (1, 3)):
                        if not (good[sh] and good[wr]):
                            continue
                        value = float(np.linalg.norm(delta[wr] - delta[sh]) / h / dt)
                        if value > 5:
                            continue
                        values.append(value)
                        if xy[ids[wr], 1] < hips[1] - .04 * h or abs(xy[ids[wr], 0] - xy[ids[sh], 0]) > .18 * h:
                            raised.append(value)
                    if values:
                        pending["values"][key].append((max(values), max(raised, default=0)))
                i = pending["index"]
                for key, values in pending["values"].items():
                    if values:
                        arms[i][key] = float(np.median([p[0] for p in values]))
                        highs[i][key] = float(np.median([p[1] for p in values]))
                        counts[i][key] = len(values)
            if time.monotonic() - last > 1:
                progress("正在分析球员动作", .52 + .46 * min(1, (float(frame.pts * frame.time_base * 1000) - info.first_pts_ms) / info.duration_ms))
                last = time.monotonic()
    if not rows:
        raise ValueError("没有可用于动作分析的人物观测。")
    signals = extract(rows, people, ball)
    signals.update(lkarm=np.array(arms), lkhigh=np.array(highs), lk_valid=np.array(counts))
    return signals
