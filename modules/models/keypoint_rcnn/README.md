# Keypoint R-CNN 人物姿态

估计人物关节点，供动作分析使用。使用现有 `pose_kpRCNN.pth`，独立调用默认使用 CPU；可显式选择 CUDA，支持将多张人物裁剪图作为一批推理。

## 调用

```python
from modules.models.keypoint_rcnn import PoseEstimator

model = PoseEstimator()
result = model(person_crop)

# 已安装可用的 CUDA 环境时，可显式指定 GPU。
model = PoseEstimator(device="cuda:0")
results = model.predict_batch([near_player_crop, far_player_crop])
```

输入为 BGR 图像，可用跟踪人物的裁剪图。结果包含 `boxes`、`scores`、`keypoints` 和 `keypoints_scores` 等 NumPy 数组。坐标相对于传入图像；场景算法负责从裁剪坐标还原到原图并选择对应人物。

可显式传入 `weight` 路径，默认权重位于 `weights/pose_kpRCNN.pth`。`device` 支持 `cpu`、`cuda` 或 `cuda:N`；不自动切换设备，不支持本接口直接选择 MPS。指定 CUDA 但环境不可用时直接报错。显存不足也直接报错，由调用方选择设备和批大小。

`predict_batch(images)` 返回与输入顺序相同的 NumPy 字典列表；`model(image)` 保持原来的单张字典返回值。空批次返回 `[]`，不计入批次或裁剪图数量。

模型和输入使用 FP32。短边目标 192、长边上限 384、RPN 候选上限 200、最终检测人数上限 3 等配置保持原值；批处理没有改变阈值或加入量化。一次批处理可能因内部补边及设备浮点计算产生数值差异，接入场景后仍需核对关节点和最终回合区间。

## 查看耗时

```python
stats = model.timings
print(model.device, stats)
```

`timings` 返回累计统计的副本，时间单位为秒：

| 字段 | 含义 |
| --- | --- |
| `initialization_s` | 本次初始化的墙钟耗时，包含依赖加载、必要的权重准备、模型加载及设备搬运 |
| `tensor_preparation_s` | 成功批次的 BGR 转 RGB、张量准备及输入搬运耗时之和 |
| `inference_and_transfer_s` | 成功批次的模型调用及结果取回 NumPy 耗时之和，包含模型内部预处理 |
| `batch_count`、`crop_count` | 已成功处理的批次及输入图数量 |

统计通过 `perf_counter` 测量，取回输出时等待相关设备结果，不额外做全局 GPU 同步或重置全局显存统计。这里不包含场景模块的视频解码、人物跟踪和光流耗时，也不能用来代替整个剪辑任务的耗时。

回合识别的个人视角入口在识别设备为 CUDA 时自动使用 CUDA，否则使用 CPU；默认批大小为 `1`，独立调用模型的 CPU 默认值保持不变。本分支保留上述累计计时接口，完整任务的阶段统计由回合模块的 `Statistics` 提供。

首轮 OPT-01 的 CPU 细分测量与 OPT-02 同帧批处理是历史试验，见[阶段报告](../../../docs/features/performance-optimization/reports/first-round.md#诊断与效果测试)。OPT-02 因漏掉仍在回合中的确认点而阻塞，不能据调用减少启用默认批处理。Windows 真实裁剪中的批处理差异另见[2026-10-21 性能报告](../../../apps/video-clipper/reports/pose-performance-20261021.md)；这些历史结果不替代最新整合版本的验证。

## 用视频测试

完成[共同环境准备](../../../README.md#开发环境)，在仓库根目录运行：

```sh
.venv/bin/python -m modules.models --model keypoint_rcnn \
  --video datasets/badminton-v1/local/ysp/test_ysp.ts --limit-s 3 \
  --output modules/models/keypoint_rcnn/.runtime/sample.jsonl
```

这个入口对整帧运行模型；回合识别内部使用人物裁剪图。权重获取规则及验证进度见[模型模块](../README.md)。
