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

Windows 2026-10-21 的 D1 CPU/CUDA 对照见[历史实测报告](../../apps/video-clipper/reports/pose-performance-20261021.md)。`codex/windows-latest` 已整合 develop `1080146` 的高级配置、统计及球路观测接口，完成三短片默认配置运行与 D1 关闭高级配置的历史区间回归，见[本轮实测记录](../../apps/video-clipper/reports/windows-latest-20261023.md)。旧素材输出一致不替代独立来源效果验收。

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

Python 调用入口是 `recognize(source, info, camera_type, weights, progress, directory, court=None, statistics=None, optimizations=None, observation_sink=None, *, pose_device=None, pose_batch_size=1)`：`info` 由媒体模块的 `probe` 提供，`weights` 可由模型模块的 `ensure_models(required_models(camera_type))` 获取，`directory` 为调用者已创建的工作目录。产品负责界面请求到这些参数的转换。

### 姿态设备与统计

个人斜侧方的姿态模型默认在当前识别设备为 CUDA 时使用该设备，其余情况使用 CPU，MPS 仍使用 CPU。可显式传入 `pose_device="cpu"` 或 `pose_device="cuda"`；指定设备不可用时直接报错。`pose_batch_size` 是正整数，默认 `1`；较大值仅合并同一观测帧内的人物裁剪，不跨帧。批处理可能因模型内部补边产生关节和动作判断差异，启用前须核对最终回合及成片。

模块使用 `statistics.py` 的可选 `Statistics` 聚合诊断；主阶段包括模型初始化、视频观测、人物与轨迹、动作分析、回合判断及中间写盘。主阶段互斥，模型、解码和传输细项嵌套其中；并行解码不能另加到总耗时。`pose_calls` 记录真实推理批次数，`person_crops` 记录输入裁剪数；实际姿态设备、批大小与模型累计计时保存在识别诊断中。2026-10-21 旧报告的 `details["performance"]` 结构不再作为当前阶段统计接口。

直接调用个人动作入口时，可传 `person_signals(..., statistics=None, *, max_fps=None, candidate_ids=None, pose_device="cpu", pose_batch_size=1, metrics=None)`；`metrics` 为需要额外诊断的调用方字典，不改变信号返回值。完整剪辑耗时由产品记录，模型自身的累计计时见[姿态模型](../models/keypoint_rcnn/README.md#查看耗时)。

命令行可用 `--pose-device cpu` / `--pose-device cuda` 和 `--pose-batch-size 1` 选择个人视角的姿态执行方式。剪辑应用 worker 对应读取 `SMASH_SUITE_POSE_DEVICE`、`SMASH_SUITE_POSE_BATCH_SIZE`；未设置时使用上述默认值。

### 文件识别配置

`optimizations` 接受 `limit_fps`、`small_input`、`grayscale`、`dynamic_scan` 四个布尔值。模块直接调用时省略的字段为关闭；产品先解析[场景默认值](../../apps/video-clipper/requirements.md#高级选项)，再显式传入完整配置。

处理顺序为源时间选帧、三帧分组、模型输入处理和回合判断。35fps 上限保留原始帧号与时间戳，三帧组及每六帧人物观测按选中帧顺序调度；个人视角第二遍选帧使用相同规则，肩腕上下文仍取锚点后第 1、3、5 个选中帧。尺寸和灰度行为由[找球模型](../models/tracknet/README.md#调用)维护。

动态粗筛只用于文件分析。每个源时间秒检查该相位首个完整三帧窗口，任一帧全局峰分数达到 0.5 即向两侧按三帧组扩展，包含首个全负停止组。同一相位的相同窗口只推理一次。C 保留基础和错位两相位及首尾补全；D 保留完整人物观测，候选控制姿态推理，已选锚点的肩腕上下文不受候选限制。跳过位置保留缺失观测与原时间，不直接裁断回合；A 用单个原分段器离线回放，不修改逐帧接口。

结果的 `recognition` 保存有效开关、帧率上限、实际网络与有效图像尺寸（高、宽）、颜色模式，以及启用粗筛时的窗口计数。导出补时仍由应用独立处理。

高视角可通过 `observation_sink` 逐条保存实际找球观测供球路分析复用；粗筛缺失位置不会作为模型观测写入，保留真实源帧号和时间。

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
