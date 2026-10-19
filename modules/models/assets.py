"""Pinned public model assets, downloaded once and verified before loading."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from filelock import FileLock


ASSETS = {
    "ball_track.pt": dict(url="https://drive.usercontent.google.com/download?id=1pCqTGJrw4ktr6_e2Li-CWeq6usxT-v6B&export=download&confirm=t", bytes=45400030,
                          sha256="0366a776d557dec4227d78555857c7ca475fd27fe8f3ac8d2f283e78349ef68b", label="找球模型"),
    "pose_kpRCNN.pth": dict(url="https://drive.usercontent.google.com/download?id=16OSGvcEhTxHAu7fN5vioTwtrZrd9tKZX&export=download&confirm=t", bytes=237101765,
                            sha256="7780185501d3631e8eb8ef6e4a322125b6e939ce3d595466075811b6465bc2c1", label="人物姿态模型"),
    "yolo11n.pt": dict(url="https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt", bytes=5613764,
                       sha256="0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1", label="人物检测模型"),
}


def digest(path: Path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


MODEL_DIRS = {"ball_track.pt": "tracknet", "yolo11n.pt": "yolo11n", "pose_kpRCNN.pth": "keypoint_rcnn"}


def ensure_models(names, directory=None, progress=lambda stage, fraction: None):
    import requests
    if not names or any(name not in ASSETS for name in names):
        raise ValueError("Specify registered model filenames.")
    directory = Path(directory) if directory is not None else None
    paths = {}
    for index, name in enumerate(names):
        asset = ASSETS[name]
        target = directory if directory is not None else Path(__file__).parent / MODEL_DIRS[name] / "weights"
        target.mkdir(parents=True, exist_ok=True)
        path = target / name
        progress("正在准备处理", index / len(names))
        with FileLock(str(path) + ".lock", timeout=120):
            if not path.is_file() or path.stat().st_size != asset["bytes"] or digest(path) != asset["sha256"]:
                partial = target / (name + ".download")
                try:
                    # Bound both connection and stalled reads. The pinned public
                    # Drive download endpoint needs no account or browser cookies.
                    with requests.get(asset["url"], stream=True, timeout=(15, 30)) as response, partial.open("wb") as output:
                        response.raise_for_status()
                        count, last = 0, 0
                        for chunk in response.iter_content(512 * 1024):
                            count += output.write(chunk)
                            if count > asset["bytes"]:
                                raise RuntimeError("下载文件超出预期大小。")
                            now = time.monotonic()
                            if now - last >= .5:
                                last = now
                                progress("正在准备处理",
                                         (index + count / asset["bytes"]) / len(names))
                    if partial.stat().st_size != asset["bytes"] or digest(partial) != asset["sha256"]:
                        raise RuntimeError("下载文件校验不通过，未加载该文件。")
                    partial.replace(path)
                except Exception as exc:
                    raise RuntimeError("准备处理失败，请稍后重试。") from exc
                finally:
                    partial.unlink(missing_ok=True)
        paths[name] = path
    return paths
