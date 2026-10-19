# Keypoint R-CNN 人物姿态

估计人物关节点，供动作分析使用。使用现有 `pose_kpRCNN.pth`，当前推理保持原方案的 CPU 设置。

## 调用

```python
from modules.models.keypoint_rcnn import PoseEstimator

model = PoseEstimator()
result = model(person_crop)
```

输入为 BGR 图像，可用跟踪人物的裁剪图。结果包含 `boxes`、`scores`、`keypoints` 和 `keypoints_scores` 等 NumPy 数组。坐标相对于传入图像；场景算法负责从裁剪坐标还原到原图并选择对应人物。

可显式传入 `weight` 路径，默认权重位于 `weights/pose_kpRCNN.pth`。

## 用视频测试

完成[共同环境准备](../../../README.md#开发工作流)，在仓库根目录运行：

```sh
.venv/bin/python -m modules.models --model keypoint_rcnn \
  --video datasets/badminton-v1/local/ysp/test_ysp.ts --limit-s 3 \
  --output modules/models/keypoint_rcnn/.runtime/sample.jsonl
```

这个入口对整帧运行模型；回合识别内部使用人物裁剪图。权重获取规则见[模型模块](../README.md)，迁移后的运行测试尚未执行。
