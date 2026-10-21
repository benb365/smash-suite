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

整理后模块导入和既有自动测试通过。原性能基线已复核A/C/D真实处理；首轮保留改动已完成单项及C/D组合检查，同帧批处理产品代码已撤回，失败证据保留。首轮独立验收通过，当前等待人工确认集成；尚未合入或推送。见[性能阶段报告](../../docs/features/performance-optimization/reports/first-round.md)。入口检查记录见[快速检查说明](../../docs/ai/2026-10-19-quick-check/notes.md)。
