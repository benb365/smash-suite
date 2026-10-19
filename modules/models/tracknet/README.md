# TrackNet 找球

使用 SoloShuttlePose 中的 TrackNet 架构和现有 `ball_track.pt` 权重，每次处理三张连续的 BGR 图像，返回三份 `ShuttlePoint(x, y, confidence)`。开启 `record_candidates` 时，`last_candidates` 另外提供各帧候选点。

## 调用

```python
from modules.models.tracknet import TrackNetPredictor

model = TrackNetPredictor(device="cpu", record_candidates=True)
points = model([frame0, frame1, frame2])
```

可显式传入 `weight` 路径。默认权重位于 `weights/ball_track.pt`；首次缺失时从固定来源下载并校验。分数来自热力图，不等于已经确认属于主球场的球，也不代表回合已经开始。

## 用视频测试

在仓库根目录、完成[环境准备](../../../README.md#开发工作流)后执行：

```sh
.venv/bin/python -m modules.models --model tracknet \
  --video datasets/badminton-v1/local/ysp/test_ysp.ts --limit-s 3 \
  --output modules/models/tracknet/.runtime/sample.jsonl
```

输出包含源帧号、时间戳、球位置和候选点。片尾不足三帧时提示并保留未处理帧数量，不补造图像。可用 `--device mps` 或 `cuda` 选择可用加速设备。

```sh
.venv/bin/python -m pytest modules/models/tracknet/tests
```

迁移后的推理尚未重测。[上游许可证](LICENSE.txt)保留在本目录。
