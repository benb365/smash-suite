# OPT-06 后续候选执行路径核查

**结论：不能把稀疏候选帧直接交给当前 `recognize()`，再把结果当作完整候选分析。** 入口内的三帧分组、检测器批次、人物选择及 D 的第二次解码都依赖完整源序列。保留原 `frame_id` 和 PTS 仍有必要，但不足以避免跨候选区间拼窗和上下文变化。现在适合做全量分析上的影子覆盖与理论工作量统计；真实跳过应作为单独实验，完整保留原始分析和所有结果差异。

## 现有入口与逐场景依赖

| 场景 | 源码路径 | 依赖完整序列的状态 | 对稀疏代理的影响 |
| --- | --- | --- | --- |
| A / `high` | `modules/rally/recognize.py:50-69`；`modules/rally/tracknet_rally.py:33-71, 73-136`；`modules/rally/rally_stream.py:22-41` | 每个送入帧都会进入 `RallyStream`；`ShuttleRallySegmenter.pending` 收满三个**收到的**帧才调用模型。点队列、运动 streak、active rally 和 quiet 超时会跨调用保留。流式校验只要求 frame ID 和时间递增，不检查相邻性；segmenter 也不会在候选区间边界自动重置。 | 两个候选区间边界两侧的帧可能被合成一个三帧模型输入；保留真实时间戳也不能恢复缺失观测。若主动清空 pending 或重置 segmenter，则会改变流状态及回合确认规则。现有入口没有“缺失模型观测”表示法。 |
| C / `courtside` | `modules/rally/recognize.py:148-232`；`modules/models/tracknet/predictor.py:66-115`；`modules/rally/scenarios/courtside.py:18-107` | `observe()` 的三帧 deque 按源 frame ID `% 3` 形成 native 和 shifted 两相重叠窗口；人物检测帧按 `% 6 == 0` 取样、每四张 flush。后续以 `features[0]` 选主球场人物并定 floor，再用全体 feature rows 建轨迹。尾部逻辑用最后 queue 的结果补 shifted 帧。 | 稀疏输入会把不同候选区间的真实帧拼入 deque；检测器批次可能跨区间，人物 flow/轨迹及全片主球场选择会改变。尾部补齐循环按 `frames_delivered` 推进，可能给未分析帧填入最后一组结果。下游还要求 native/shifted 帧 ID 与时间戳逐项匹配（`shuttle_paths.py:41-56`）。 |
| D / `personal` | `modules/rally/recognize.py:148-232, 235-350`；`modules/rally/common/players_v2.py:11-93`；`modules/rally/common/feet.py:4-22`；`modules/rally/scenarios/personal.py:11-97` | 第一遍仍按 frame ID `% 6 == 0` 做人物检测，每四帧 flush；Farneback 使用相邻 detector feature 的 `previous_gray/previous_time`。之后 `track_all()`、`select()`、`follow()` 用全体 features 建立和筛选人物轨迹；`select()` 明确以观测数、活动范围、两轨重叠筛选全片人物。D 随后在 `person_signals()` 重新用 PyAV 从头逐帧解码，以 frame ID 找 anchors，对每个 anchor 运行姿态模型；肩腕 LK 只比较 anchor 后第 1、3、5 帧。脚点与动作分析再对这些时序信号做邻域平滑/上下文计算。 | 第一遍稀疏源会改变人物 batch、光流间隔及全片球员身份选择。只代理 `FileFrameSource` 不会筛掉第二遍的全片解码；稀疏 anchor 会改变姿态调用及 LK 支持帧，并让后续时间窗落在不同的时间采样上。要跳过 D，两个 pass 必须分别定义候选门控，不能只包一层源帧迭代器。 |

`FileFrameSource` 产出连续分配的 `frame_id`、以首个 PTS 归零的实际时间戳；它的 `limit_s` 只支持截取前缀，不支持候选区间筛选（`modules/media/video_input.py:18-44, 69-116, 141-163`）。`recognize()` 接收路径并在函数内直接创建该 source，D 第二遍也直接 `av.open(source)`（`modules/rally/recognize.py:32, 57, 191, 250-263`），因此当前没有可传入的 source factory。代理若仍完整解码、只过滤交付帧，也不会节省解码成本。

## 最小完整试验边界

1. 先完成 D 当前粗查。随后在全量原分析不变的前提下，只统计候选三帧组与原识别区间的覆盖、对齐到原生模型调用相位后的可门控调用数和对应工作量比例；此项是影子分析，不跳过调用，不称净提速，也不把当前保留回合当运行时 oracle。
2. 若再做真实跳过，保持完整源帧、源 PTS 和原 frame ID 供上下文使用，在模型调用边界按**原生合法三帧窗口**门控，不把分散帧拼成一窗。完整保留原始分析结果；候选版只作为实验输出并逐项保留差异、漏检风险和失败案例。
3. C/D 的实验门控需让未运行模型的原生窗口显式表现为“无观测”，保持原 frame ID/时间对齐；不得调用现有 shifted 尾部补齐为未分析帧造候选。D 还需单独决定是否保留全量人物/光流/姿态上下文；若筛减这些路径，人物身份及动作信号已不再与原分析等价，必须作为独立实验记录。
4. A 当前 segmenter 没有缺失观测输入，也没有分段重置契约。真实跳过 A 前需在实验边界明确如何表示未推理帧、怎样处理三帧 pending 和跨段 active rally；不能用稀疏 source proxy 或虚构图像来绕过该缺口。

这项核查没有授权改产品行为或删除区间。A/C 的已知影子扫描分别覆盖 5/5、9/9 当前原始区间，但这些命中只支持继续做候选诊断；它们不证明未命中的其它活动不存在，也不构成准确率/召回验收。D 结果待本轮扫描完成后补入比较。
