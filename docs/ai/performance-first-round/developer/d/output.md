# D 线第 2 轮交付

## 当前实现

用户决定本轮暂缓批处理。已按 `controller/variants/opt02-batch.patch` 反向撤销 D 线合批增量：删除 `PoseEstimator.predict_batch`，移除同帧批次收集、批次/裁剪尺寸统计，恢复逐人 `model(crop, statistics=stats)` 调用与原有 `pose_calls`、`person_crops` 单次累加。C 线 `observe` 未修改。

保留 OPT-01 单图细分计时，以及 OPT-04 姿态 RGB copy 精简。`cvtColor` 结果直接转为张量，未重新增加额外 `.copy()`。历史 `d02-batch.patch` 与批处理失败证据保留作追溯，当前交付不应用该补丁；当前源码阶段为 OPT-01 + OPT-04。

Keypoint README 保留 Statistics 计时说明，并注明回合识别仍在 CPU 上逐个人物裁剪调用；保留首轮合批提前截断有效回合的失败结论及报告链接。

## 测试与 SHA

删除只覆盖批处理路径的 `test_pose_batch.py`，替换为 `test_pose_statistics.py`，只检查启用统计时的单图分项记录，以及关闭统计时输出不变且不读取时钟。

- `.venv/bin/python -m pytest -p no:cacheprovider modules/rally/tests/test_pose_statistics.py -q`：1 项通过。
- `git diff --check`：通过。
- 未运行模型、真实探针或完整测试。

当前完整源文件 SHA-256：

- `modules/models/keypoint_rcnn/__init__.py`: `379ed20f3c6e228efecd08828ee8b6b6dc6a89084dd19173163ef1cab9c19316`
- `modules/rally/recognize.py`: `ee2c0a949522ab6c809bf7da9afb4a4956dda9ad3b6da4fc389e8f0598e8bcd0`

阶段补丁顺序为 `d01-statistics.patch` → `d04-copy.patch`；`d02-batch.patch` 保留作失败候选记录，不属于当前实现。待主控执行正式 D 组合测量。
