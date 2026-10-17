# 系统边界

Smash Suite 当前没有被接受的内部算法架构。本文只固定算法选择前必须保持稳定的输入、输出与在线处理边界；运动、人物、姿态、球轨迹、音视频或端到端时序模型都只是待评估候选。

## 数据流

```text
帧生产者
  │
  ▼
TimestampedFrame ──► Rally Segmenter（实现待选型）──► RallyInterval
                          │
                          ▼
                  可选诊断与评估记录
```

正式边界从 `TimestampedFrame` 开始，到 `RallyInterval` 结束。摄像头、网络协议、文件容器和界面不属于分割器契约。

本地视频 replay 负责按时间顺序生成帧，只是 benchmark 和调试适配器，不是正式输入协议。评估器消费预测区间和人工标注，也不参与线上推断。

## 输入概念

```text
TimestampedFrame(
  frame_id,
  timestamp_ms,
  image
)
```

- `frame_id`：流内唯一、递增的帧标识。
- `timestamp_ms`：帧在源时间轴上的毫秒时间戳，必须严格单调递增。
- `image`：当前帧图像；具体像素格式由实现边界外的适配层统一。
- 分割器只能消费当前帧和已有历史状态，不得读取未来帧。
- 时间戳乱序、重复或回退属于输入契约错误，不要求核心算法兼容。

## 输出概念

```text
RallyInterval(
  rally_id,
  start_ms,
  end_ms,
  emitted_at_ms,
  confidence?,   # 可选
  diagnostics?   # 可选
)
```

- `rally_id`：流内唯一的回合标识。
- `start_ms`、`end_ms`：完整回合在源时间轴上的闭区间，满足 `start_ms <= end_ms`。
- `emitted_at_ms`：分割器确认回合结束并输出结果时对应的源时间戳，满足 `end_ms <= emitted_at_ms`。
- `confidence` 和 `diagnostics` 只用于比较与排障，不是调用方依赖的必填字段。

一个回合只在结束被确认后输出一次。算法可以在内部保留候选开始点，并在输出时回填 `start_ms`；当前契约不提供“开始事件”、区间修订或撤回协议。

## 实现级契约与回放

`backend/app/vision/rally_stream.py` 定义 `TimestampedFrame`、`RallyInterval`、
候选算法的 `process(frame)` 契约和输入输出校验器 `RallyStream`。首版
`frame_id` 与 `rally_id` 使用整数。真实帧生产者和 benchmark 回放均通过
`RallyStream.process` 调用候选算法；这不表示任何内部算法已经选型。

校验器在调用算法前拒绝非有限、重复或回退的时间戳，以及不递增的帧标识；
输出必须满足区间时间顺序、回合标识唯一，并且 `emitted_at_ms` 等于当前
输入帧的源时间戳。流结束不是回合结束证据；回放不调用 EOF flush，不补造
未确认回合的完整区间。

`replay_frames` 按需逐帧消费输入，不提前读取未来帧；记录预测、实际消费
帧数、墙钟耗时和实时处理倍率。调用方提供该次回放实际覆盖的源时长，
不得用整场时长计算短窗口的处理倍率。

`iter_cfr_video_frames` 仅适用于数据清单明确声明恒定帧率的文件：源时间戳
为零起点帧号除以清单帧率，抽样不重编号。可变帧率或真实采集源须自行
提供实际源时间戳，不在该适配器内猜测帧率或补齐缺帧。

## 文件输入模块

`backend/app/vision/video_input.py` 的 `FileFrameSource` 是输入边界外的文件
适配器，输出仍为 `TimestampedFrame`；模型选择及区间契约不受来源影响。
它用 PyAV 解码原始 BGR 图像，以首帧 PTS 为零点保留源时间间隔，缺失、
重复或回退的时间戳会明确报错，不按估计 fps 伪造时间。

`offline` 模式尽快处理文件；`realtime` 模式按单调时钟的启动时刻加源
时间调度。一个输入线程与一个推理消费者之间最多排队六帧；源分辨率与
帧率保持不变，文件结束不强制输出未结束回合。实时模式中，最旧排队、
待提交或正在处理帧落后计划时刻超过五秒，终止本次分析并保留诊断。
离线模式只施加有界阻塞，不使用实时超时。

文件模拟的墙钟延迟与源时间轴上的 `emitted_at_ms` 分开记录；正式输出
仍只包含源时间。模拟延迟不包含真实手机或摄像头在采集、编码、网络传输
中的耗时。后续设备/网络适配器实现同一帧输入契约；当前不注册未实现的
来源，也不改变旧 Motion/Speed 实验的 HTTP 接口。

## 尚未确定的内部架构

当前不指定检测器、跟踪器、姿态模型、状态机、特征融合方式或模型部署形式。候选路线必须使用相同输入输出契约和统一 benchmark 比较，形成选型记录后，才能在本文增加被接受的内部组件和数据流。

仓库中现存实现属于 legacy experiment。它可以帮助识别失败模式，但不能证明某个算法组件已经被选中，也不能作为新实现必须兼容的接口。

## 验证边界

首份 benchmark 使用仓库现有样片、ROI 和 verified 人工回合标注作为种子数据。旧 trace、参数和效果结论不继承；可复现评估口径见[回合分割需求与评估](plan/rally-segmentation-requirement.md)，执行顺序见[当前路线图](plan/roadmap.md)。
