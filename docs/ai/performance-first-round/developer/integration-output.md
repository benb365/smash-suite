# 集成准备结果

轮次：integration-1
工作区：`codex/performance-first-round`，基点及当前 HEAD 为 `55c6f0c13c4eff35dc960da6328359711117afda`

## 修改

- 姿态实现恢复为单图 `PoseEstimator(image)`，仅保留 OPT-04 已验证的额外 `.copy()` 删除；识别入口改回 `model(crop)`，保留原 `pose_inference_s`、调用数及裁剪数统计。
- 删除只验证 OPT-01 细分接口的 `modules/rally/tests/test_pose_statistics.py`。OPT-03 缓存测试保留。
- 更新性能专题入口、首轮方案和报告，以及 Keypoint R-CNN、模型、TrackNet、自动剪辑的 README：明确本轮只准备集成 OPT-03/04；OPT-01 保留诊断结论和历史证据；OPT-02 因 D 找球后的算法稳健性依赖而阻塞，并记录恢复条件。
- 新增本结果文件。未修改 `task.md`、路线图或测量原始数据。

## 静态检查

- `modules/models/keypoint_rcnn/__init__.py` 与 `5c946e9` 版本相比仅去掉 RGB 转换结果上的 `.copy()`；逐字差异检查通过。
- `modules/rally/recognize.py` 与当前 HEAD 相比仅移除姿态调用的 `statistics=stats` 实参；逐字差异检查通过。
- `modules/models/tracknet/predictor.py` SHA-256 为 `df737b3bac7ae2ecba2a8ce6337cb56d7350cc053de54f4b950d997a634679aa`，与 HEAD 相同；OPT-03 测试 `modules/models/tracknet/tests/test_preprocessed_cache.py` SHA-256 为 `7c60f4d9525216a9dad60574c7bf28b2d9475d08f162b4fb572bb9702ad62fc7`，与 HEAD 相同。
- 姿态模型调用仍为逐人单图，未发现新增批处理实现；姿态细分计时接口和对应测试已移除。
- 两个新增或调整的相对文档链接及标题锚点均可解析。`git diff --check` 通过。

## 版本边界与待验收

- 保存的测量版本包含 OPT-01 细分诊断；交付代码只含 OPT-03/04。本轮未为删除诊断后的交付版本新增性能测量，历史秒数不作为该版本的新基线。
- OPT-04 C 递进识别耗时增加 1.07%，原因和可重复性仍未验证；没有将其描述为稳定提速或已证明退化。
- 原首轮 106 项通过记录保留为历史测量/验收版本记录。本轮最终代码测试和必要数值对照留待独立验收另行记录；本轮未运行后端测试、模型或性能实验。
- 用户已确认 OPT-03/04 集成；当前仅准备合入，尚未合入或推送。OPT-02 恢复前需先改善并独立验收 D 找球后的算法稳健性，再以改进后的逐人姿态结果复验批处理的已知点和完整区间/导出，通过后再检查组合。
