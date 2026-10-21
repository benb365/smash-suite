# TrackNet 找球

使用 SoloShuttlePose 中的 TrackNet 架构和现有 `ball_track.pt` 权重，每次处理三张连续的 BGR 图像，返回三份 `ShuttlePoint(x, y, confidence)`。开启 `record_candidates` 时，`last_candidates` 另外提供各帧候选点。

## 调用

```python
from modules.models.tracknet import TrackNetPredictor

model = TrackNetPredictor(device="cpu", record_candidates=True)
points = model([frame0, frame1, frame2])
```

可显式传入 `weight` 路径。默认权重位于 `weights/ball_track.pt`；首次缺失时从固定来源下载并校验。分数来自热力图，不等于已经确认属于主球场的球，也不代表回合已经开始。

## 重叠帧复用

C 场边观测可传 `frame_ids=[id0, id1, id2]`，按同一视频的帧号复用最多3份CPU预处理张量。它只减少颜色转换、浮点及缩放的重复计算，每组模型仍照常推理。普通 `model(frames)` 调用不启用缓存。

帧号必须对应同一视频中的同一幅图像。观测完成或失败后调用 `clear_preprocessed_cache()`；复用实例处理另一视频前也须清空，避免帧号重用串图。C识别入口已用清理逻辑保证此生命周期。[首轮阶段证据](../../../docs/features/performance-optimization/reports/first-round.md)记录张量、模型输出与完整剪辑对照。

## 用视频测试

在仓库根目录、完成[环境准备](../../../README.md#开发环境)后执行：

```sh
.venv/bin/python -m modules.models --model tracknet \
  --video datasets/badminton-v1/local/ysp/test_ysp.ts --limit-s 3 \
  --output modules/models/tracknet/.runtime/sample.jsonl
```

输出包含源帧号、时间戳、球位置和候选点。片尾不足三帧时提示并保留未处理帧数量，不补造图像。可用 `--device mps` 或 `cuda` 选择可用加速设备。

```sh
.venv/bin/python -m pytest modules/models/tracknet/tests
```

真实TrackNet推理、C缓存单项与组合、A复制简化完整输出已复核；用户已确认集成首轮 OPT-03/04，当前准备合入。[上游许可证](LICENSE.txt)保留在本目录。
