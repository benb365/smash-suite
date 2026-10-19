# YOLO11n 人物检测

检测图像中的人物，返回原图坐标中的人物框和分数。主场选人、持续跟踪和回合判断由场景算法完成。

## 调用

```python
from modules.models.yolo11n import PersonDetector

model = PersonDetector(device="cpu")
boxes_per_image = model([image], confidence=.2, image_size=960)
```

输入为 BGR 图像列表；每张图对应一组 `x1/y1/x2/y2/confidence` 字段。可显式传入 `weight`，默认使用本目录 `weights/yolo11n.pt`。

## 用视频测试

完成[共同环境准备](../../../README.md#开发工作流)，在仓库根目录运行：

```sh
.venv/bin/python -m modules.models --model yolo11n \
  --video datasets/badminton-v1/local/ysp/test_ysp.ts --limit-s 3 \
  --output modules/models/yolo11n/.runtime/sample.jsonl
```

输出逐帧时间与人物框。权重获取规则及验证进度见[模型模块](../README.md)。
