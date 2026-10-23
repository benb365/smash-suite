# OPT20：移除 D 场景未使用的全画面光流

## 结论

本轮 D-short 产品 API 对照中，移除 Farneback 及只服务于它的中间数据后，基线与候选的 13 段 raw 回合、13 个 padding 500 ms 导出区间、`decisions.json` 和 13 个 `person-signals.npz` 数组逐值相同。候选完整执行 Pose 与决策，选中 track IDs 仍为 `[58, 40]`。这支持本样片上的行为等价。

视频约 250.9 秒，不是 30 分钟验收；没有匹配人工标注，不作准确率结论。每种方案仅一次运行，不能据此声称稳定性能收益。

## 单次产品 API 计时

| 阶段 | 基线 | 候选 |
| --- | ---: | ---: |
| 准备 | 0.579 s | 0.571 s |
| 识别 | 308.514 s | 252.989 s |
| 成片 | 12.924 s | 12.803 s |
| 总计 | 322.017 s | 266.362 s |

识别单次相差 55.526 秒。两次为串行独立产品 API 运行；这是一次观测，不是稳定收益承诺。

## 等价与工作量

视频 SHA256 `360e3de1018a9656770ea432c903afba44cff29c0052f03ea65606a5200867fd`，输入清单 SHA256 `afd60a8dbb0930948faf6962fb881b27e27fc42d8dc4f395ff923695f27d8ec4`，ball/YOLO/Pose 权重 SHA 在 summary 中列明且两边相同。两边记录的依赖版本、MPS 自动模型设备、Pose CPU、Torch 4 / OpenCV 1 线程相同。均处理 7527 帧两遍，执行 2432 次 Pose 调用、转换 5018 帧；选中 track IDs 均为 `[58, 40]`。

person-signals 数组均以 `equal_nan=True` 精确相同：times、arm、high、ready、pickup、speed、present、ball、lkarm、lkhigh、lk_valid、foot_speed、foot_valid。`decisions.json` 与成片 MP4 SHA 相同；完整成片解码对照确认 raw/export、输出时长、质量、告警、音视频流结构与解码帧数相同。逐项预测、数组维度、阶段统计、采样资源以及输入/权重/source SHA 见 [summary.json](summary.json)。

主控报告后端检查为 107 passed（13.10 秒，1 warning）；此处标记为主控提供，本报告回合未重跑。

## 证据入口

- 基线：primary 保存目录 `apps/video-clipper/.runtime/opt20-flow/baseline/D-short/evidence/`，报告 `apps/video-clipper/.runtime/opt20-flow/baseline-report.json`。
- 候选：本工作树 `apps/video-clipper/.runtime/opt20-flow/candidate/D-short/evidence/`，报告 `apps/video-clipper/.runtime/opt20-flow/candidate-report.json`。
