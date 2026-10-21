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

A 保留原逐帧方案，C/D 已接入确认的改进并继续通过文件分析使用。当前评估纳入 A/C/D，B 继续暂缓。历史整理检查曾记录 16 份保存观测输出一致；其输入缓存现已缺失，旧检查入口已移除，不能作为当前可复验的证据。已知漏回合、边界和间歇问题仍待处理，独立来源验收未完成。记录见[算法确认报告](experiments/reports/algorithm-decisions-20261019.md)和[整理后快速检查](../../docs/ai/2026-10-19-quick-check/notes.md)。

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

按[项目首页](../../README.md#开发环境)准备环境，在仓库根目录执行：

```sh
.venv/bin/python -m modules.rally --scene high \
  --video datasets/badminton-v1/local/ysp/test_ysp.ts \
  --output modules/rally/.runtime/sample-high
```

其他场景使用 `--scene courtside` 或 `--scene personal`；必要时用 `--court '[[0,0],[1,0],[1,1],[0,1]]'` 传入四个归一化主场角点。输出 `result.json` 包含原始回合区间、识别说明和设备信息，不导出成片，不施加产品的前后补时。

Python 调用入口是 `recognize(source, info, camera_type, weights, progress, directory, court=None)`：`info` 由媒体模块的 `probe` 提供，`weights` 可由模型模块的 `ensure_models(required_models(camera_type))` 获取，`directory` 为调用者已创建的工作目录。产品负责界面请求到这些参数的转换。

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

`common/` 保存共用处理步骤，`scenarios/` 保存场景组合与参数，`evaluation/` 提供评分；`experiments/` 保存诊断入口，运行文件放 `.runtime/`。历史试验源码归档到 `backup/`，不由产品动态导入。

```sh
.venv/bin/python -m pytest modules/rally/tests
```

当前自动测试使用合成输入校验流式契约和算法规则。真实视频须从上方场景入口重新推理，不能由旧缓存检查替代。本轮性能任务已按[性能基线报告](../../apps/video-clipper/reports/performance-baseline.md)完成三份真实短片的统计开关对照，原始识别区间与成片结构均一致；该对照不代表准确率验收。更多入口见[实验说明](experiments/README.md)。

原文件输入诊断入口保留为 `modules.rally.experiments.run_live_tracknet`，支持 `offline/realtime`、固定重复和处理日志；`run_tracknet` 保留已确认恒定帧率素材的早期基线入口。
