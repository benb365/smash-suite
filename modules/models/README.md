# 模型推理

模型接收图像并输出识别结果，供场景算法或独立实验调用。回合判断不在模型模块内完成。

| 模型 | 输入与输出 | 说明 |
| --- | --- | --- |
| TrackNet | 连续三帧 → 球坐标、分数及候选点 | [调用与测试](tracknet/README.md) |
| YOLO11n | 图像 → 人物位置框 | [调用与测试](yolo11n/README.md) |
| Keypoint R-CNN | 人物裁剪图或图像 → 人物框与关节点 | [调用与测试](keypoint_rcnn/README.md) |

## 环境与文件

先按[项目首页](../../README.md#开发环境)安装共同环境。主要依赖 PyTorch、Torchvision、Ultralytics、OpenCV 和 NumPy；权重下载使用 Requests 和 Filelock。

每个模型的代码、配置与 README 位于对应目录，开发权重放在该目录的 `weights/`，不提交 Git。`assets.py` 记录固定下载来源、大小和 SHA256；缺失权重首次使用时下载并校验，之后离线复用。已迁移现有的三个在用权重。

产品可显式传入自己的权重路径或缓存目录；不会因此向模块目录写入产品任务数据。独立实验的输出文件建议放到对应模型的 `.runtime/`。

## 公共检查入口

```sh
.venv/bin/python -m pytest modules/models
```

共同环境要求 Python 3.9+。

## 当前进展

原性能基线已复核 A/C/D 真实处理；首轮帧预处理复用和删除冗余复制已合入 develop，后续原地归一化减少分配及产品高级配置分别记录于[性能专题](../../docs/features/performance-optimization/README.md)。早期 CPU 姿态细分诊断和多人批处理试验的结论仍保留，不能将调用次数减少当作效果通过。

独立调用 `PoseEstimator()` 默认 CPU；可显式选择 CUDA，默认批大小由调用方控制。回合模块的个人视角入口在 CUDA 可用时自动选择 CUDA，默认逐张推理；设备支持、累计计时及批处理差异见[姿态接口](keypoint_rcnn/README.md)。

Windows 的固定权重 D1 对照见[2026-10-21 实测报告](../../apps/video-clipper/reports/pose-performance-20261021.md)。当前 `codex/windows-latest` 正在整合最新 develop，本轮模型与高级配置联用仍待实际验证；旧报告不代表当前整合版本通过。此前入口检查记录见[快速检查说明](../../docs/ai/2026-10-19-quick-check/notes.md)。
