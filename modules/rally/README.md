# 回合识别

按拍摄场景组合模型推理、人物跟踪、轨迹与动作判断，输出回合在源录像上的时间区间。模块同时提供效果评估和实验入口，不依赖剪辑产品的请求或任务状态。

回合定义和使用条件见[识别需求](requirements.md)，测试数据与评分方式见[评估规范](evaluation.md)。

## 场景方案

| 参数值 | 拍摄场景 | 当前方案 |
| --- | --- | --- |
| `high` | 官方比赛高视角（A） | 原球轨迹方案，参数保持不变 |
| `courtside` | 场边低视角（C） | 原短段过滤、拆分内部间歇、尾部候选连接；`tail_gap800_growth300` |
| `personal` | 个人斜侧方（D） | 人物动作结合球点、对手活动和脚点移动；确认记录中的 `candidate` |

配置见 [profiles.json](scenarios/profiles.json)，来源见 [selection.json](scenarios/selection.json)。原确认结果见[算法记录](experiments/reports/algorithm-decisions-20261019.md)。

A 可以逐帧调用，确认结束后输出完整回合；C/D 会使用后续信息，当前通过文件分析入口调用。

## 当前进展

A 保留原逐帧方案，C/D 已接入确认的改进并继续通过文件分析使用。当前评估纳入 A/C/D，B 继续暂缓。整理后 16 份保存观测回放与确认结果逐项一致；这不等于重新运行模型或验证真实视频效果。已知漏回合、边界和间歇问题仍待处理，独立来源验收未完成。记录见[算法确认报告](experiments/reports/algorithm-decisions-20261019.md)和[整理后快速检查](../../docs/ai/2026-10-19-quick-check/notes.md)。

Windows 本机已对同一 D1 完成真实模型 CPU/CUDA 姿态性能对照，原始回合区间和成片保持相同；阶段计时、批次限制及原有边界缺陷见[实测报告](../../apps/video-clipper/reports/pose-performance-20261021.md)。该诊断素材结果不替代独立来源效果验收。

## 输入输出与职责

模块消费[媒体模块](../media/README.md#帧与时间)的 `TimestampedFrame`，输出源时间轴上的回合区间。模型观测由[模型模块](../models/README.md)提供，例如 TrackNet 的 `ShuttlePoint`。文件容器、摄像头、网络协议、视频预览和编码导出由调用方或输入适配器处理，不属于回合判断职责。当前不提供击球动作分类、精彩时刻或球速结果。

流式入口在 `rally_stream.py` 中定义 `process(frame) -> Sequence[RallyInterval]`，只使用当前帧和历史状态。`RallyStream` 校验整数且严格递增的帧标识，以及有限且严格递增的源时间戳；不兼容乱序、重复或回退输入。

`types.py` 定义的 `RallyInterval` 包含四个字段：

| 字段 | 约定 |
| --- | --- |
| `rally_id` | 流内唯一的整数回合标识 |
| `start_ms`、`end_ms` | 完整回合在源时间轴上的毫秒闭区间，满足 `start_ms <= end_ms` |
| `emitted_at_ms` | 确认并输出回合时的源时间戳，满足 `end_ms <= emitted_at_ms`；流式校验器要求它等于当前输入帧时间 |

每个已确认回合只输出一次。算法可以延迟确认结束并回填开始点；未确认候选保留在内部，不提供开始事件、区间修订或撤回协议。文件结束不是回合结束证据，流式回放不在 EOF 时补造完整区间。额外置信度或诊断证据不属于上述四字段类型的必填内容。

上述逐帧约定适用于流式入口；C/D 文件分析允许后续上下文，不据此宣称符合流式要求。原始识别区间与应用的补时、裁界、合并和导出区间分开保存，不用导出区间替代算法结果评分。

## 运行场景算法

按[项目首页](../../README.md#开发工作流)准备环境，在仓库根目录执行：

```sh
.venv/bin/python -m modules.rally --scene high \
  --video datasets/badminton-v1/local/ysp/test_ysp.ts \
  --output modules/rally/.runtime/sample-high
```

其他场景使用 `--scene courtside` 或 `--scene personal`；必要时用 `--court '[[0,0],[1,0],[1,1],[0,1]]'` 传入四个归一化主场角点。输出 `result.json` 包含原始回合区间、识别说明和设备信息，不导出成片，不施加产品的前后补时。

Python 调用入口是 `recognize(source, info, camera_type, weights, progress, directory, court=None, *, pose_device=None, pose_batch_size=1)`：`info` 由媒体模块的 `probe` 提供，`weights` 可由模型模块的 `ensure_models(required_models(camera_type))` 获取，`directory` 为调用者已创建的工作目录。产品负责界面请求到这些参数的转换。

个人斜侧方的姿态模型默认在当前识别设备为 CUDA 时使用该设备，其余情况使用 CPU，MPS 仍使用 CPU。可显式传入 `pose_device="cpu"` 或 `pose_device="cuda"` 比较同一输入；显式指定的设备不可用时直接报错。`pose_batch_size` 是正整数，默认 `1`；较大值仅合并同一观测帧内的人物裁剪，不跨帧，不改变帧采样、裁剪范围、关节筛选或后续光流判断顺序。

返回的 `details["performance"]` 使用 `perf_counter` 记录 `model_setup_s`、`observe_s`、`person_tracking_s`、`candidate_motion_s`、`person_signals_s`、`scenario_decision_s` 和 `total_s`。模型构造计入 `model_setup_s`，从对应的观测和人物信号阶段扣除；YOLO 在首次预测时进行的设备初始化和预热仍计入观测阶段的 `yolo_wall_s`，该字段不代表纯前向耗时。总耗时还包含进度回调、导入及结果写入等开销。高视角的逐帧识别和决定交织进行，统一计入 `observe_s`，并由 `observe_includes_scenario_decision` 标明，不另外补造决定阶段的耗时。

C/D 的 `performance["observe"]` 细分归一化图像准备 `frame_prepare_s`、人物检测 `yolo_wall_s`、外观描述 `descriptor_wall_s` 和灰度准备/Farneback 光流/身体活动 `farneback_body_motion_wall_s`。`tracknet` 累计每次模型的 `preprocess_s`、`inference_and_transfer_s`、`point_decode_s`，另记外层 `wall_s`、调用数、输入帧次数及 native/shifted/tail 调用数；重复输入的帧按实际调用计数，尾部调用同样计入。`input` 原样保留 `FileFrameSource.stats`，其中解码与像素转换发生在生产线程，可以和消费侧工作重叠；它们用于解释热点，不能加成互斥阶段或与外层总时钟重复相加。

个人动作入口 `person_signals(source, info, people, ball, weight, progress, *, pose_device="cpu", pose_batch_size=1, metrics=None)` 保持原返回值，可将性能细项写入调用者传入的字典。该字典也由 `recognize` 放入 `performance["person_signals"]`：`decode_s` 记录容器打开与逐帧解码等待，`frame_prepare_s`、`crop_prepare_s` 记录图像准备，`pose_wall_s` 记录姿态批次调用，`pose_selection_s` 记录人物匹配，`flow_s` 记录后续 LK 光流与统计，`extract_s` 记录信号提取；另含帧数、设备、批大小和包含模型初始化的 `total_s`。`pose_model` 原样保留模型的 `initialization_s`、`tensor_preparation_s`、`inference_and_transfer_s`、`batch_count` 和 `crop_count`。这些嵌套项用于解释阶段内部成本，不能与外层阶段重复相加；输出已取回 CPU 后无需额外同步 CUDA。

命令行可用 `--pose-device cpu` / `--pose-device cuda` 和 `--pose-batch-size 1` 选择个人视角的姿态执行方式。剪辑应用 worker 对应读取 `SMASH_SUITE_POSE_DEVICE`、`SMASH_SUITE_POSE_BATCH_SIZE`；未设置时使用上述默认值。

## 效果评估

```sh
.venv/bin/python -m modules.rally.evaluation \
  --predictions modules/rally/.runtime/sample-high/result.json \
  --annotations datasets/badminton-v1/annotations/seed/ysp/rally-segment-manual.json \
  --output modules/rally/.runtime/sample-high/evaluation.json
```

标注路径必须与实际视频对应，并已通过人工审核。指标包括回合漏检、误报、误切、误合并和起止边界误差，具体口径见[评估规范](evaluation.md)。不同候选使用相同输入和规则；样片、标注、算法与配置保留版本。种子素材和标注字段见[数据规范](../../datasets/requirements.md)。

流式 `replay_frames` 按需逐帧消费输入，不预读未来帧，记录预测、实际消费帧数、墙钟耗时和实时处理倍率。调用方通过 `source_duration_ms` 提供本次实际覆盖的源时长，不能用整场时长计算短窗口倍率；评估器不参与在线推断。

## 实验与自动测试

`common/` 保存共用处理步骤，`scenarios/` 保存场景组合与参数，`evaluation/` 提供评分；`experiments/` 保存诊断及回放入口，运行文件放 `.runtime/`。历史试验源码归档到 `backup/`，不由产品动态导入。

```sh
.venv/bin/python -m pytest modules/rally/tests
.venv/bin/python -m modules.rally.experiments.replay \
  --output modules/rally/.runtime/migration-replay.json
```

回放入口使用 16 份保留的 A/C/D 观测，检查所选方案是否与确认记录逐条一致，不运行模型；它不能替代从视频运行的完整验证。共用缓存的片段按用例声明的窗口截取，并将帧号和时间归零，详见[实验入口说明](experiments/README.md)。

原文件输入诊断入口保留为 `modules.rally.experiments.run_live_tracknet`，支持 `offline/realtime`、固定重复和处理日志；`run_tracknet` 保留已确认恒定帧率素材的早期基线入口。
