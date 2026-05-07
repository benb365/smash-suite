# 执行路线图

本文档是当前 MVP demo 的有序实施计划，属于 `docs/plan/` 作战手册。它需要随代码持续更新：任务落地后，更新对应里程碑的状态、证据和缺口。

## Demo 目标

Smash Suite 当前目标是 **Android 智能摄像头节点 + PC 测速工作站**。

- Android 负责高帧率羽毛球视频采集、粗场景过滤、上传有价值片段或候选事件。
- PC 负责 Android 服务控制、片段接收、场地标定、所有测速分析、资产管理和结果展示。
- Android 阶段性不做产品 UI。PC Web 是唯一控制中心。

## Current Focus

**P0 / M2a PC Offline SceneGate / In Progress**

当前最高优先级是在 PC 离线侧验证 SceneGate baseline，并从纯 motion baseline 转向模型辅助 baseline。当前代码已能输入本地视频并输出主时间线 `idle` / `rally` JSON，将 `smash_candidate` 作为嵌套在 `rally` 内部的候选区间，并用 `data/samples/manual_scene` 自动评估 precision / recall / F1。人工标注显示当前 motion baseline 与真实 rally 差距较大；SoloShuttlePose PC spike 脚本和 adapter 已落地，adapter 已能解析上游 `res/videos/<video>/<video>_<begin>-<end>.mp4` rally clip 文件名，外部仓库和四个 runtime 权重也已从本地 zip 安装到 `models/SoloShuttlePose`。最新 PC-only spike 已确认 SoloShuttlePose 能加载权重，但在 `test001.mp4` 上游 court 预处理扫到 9250 / 9269 帧后失败，未产出 rally clips；为节省本机资源，net 预处理跑到 1015 帧后中止并记录为 `run_failed`。下一步不要继续盲跑完整 SoloShuttlePose，而是先做人工失败归因、评估 reference-frame / crop 是否值得尝试，或改走 TrackNetV3 + hitting-event detector。这个任务先于 Android 正式移植，因为过滤策略需要先用可调、可观测、可回放的 PC pipeline 验证。

第一批交付物：

- 后端 SceneGate 契约，`SceneSegment` 至少覆盖 `category`、`start_ms`、`end_ms`、`confidence`、`reason`、`source_frame_range`，`SceneCandidate` 表示嵌套 `smash_candidate`。（已落地）
- PC 离线 SceneGate baseline，可读取本地视频文件、按 ROI 分析并生成分段 JSON。（已落地）
- 最小验证记录格式，能记录人工 smash 区间、算法命中区间、漏检情况和保留视频比例。（已落地模板，待人工填写）
- 文档补充当前阈值、失败案例、manual_scene 指标和下一轮 model spike 方向。

建议代码入口：

- 数据类型：`backend/app/models.py`。
- 自动评估：`backend/app/vision/scene_eval.py`。
- 现有视频读取和 OpenCV pipeline：`backend/app/vision/pipeline.py`。
- 现有运动检测 baseline：`backend/app/vision/detectors.py`。
- 后端测试和离线脚本：`backend/tests/`。

验收方式：

- `pnpm run test:backend`。
- `pnpm run typecheck:frontend`，仅当前端类型或共享契约变化时需要。
- `git diff --check`。
- roadmap 的 M2a 里程碑补齐代码路径、运行命令或示例 JSON、验证样片记录路径。

## 当前优先级

| 优先级 | 里程碑 | 状态 | 说明 |
| --- | --- | --- | --- |
| P0 | M2a PC Offline SceneGate | In Progress | 当前最高优先级：用 manual_scene 指标评估 PC 离线 baseline，并推进模型辅助 SceneGate spike。 |
| P1 | M1 PC Controls Android | Next | Android 服务控制是 SceneGate 可迁移后的设备链路基础。 |
| P1 | M2b Android Timeline Filtering | Todo | 将 PC 验证过的 SceneGate 迁移到 Android，在上传前降低数据量。 |
| P2 | M3 PC Calibration + Speed Analysis | Todo | PC 将 Android 片段转成标定后的测速结果。 |
| P3 | M4 Validation + Demo Hardening | Todo | 用真实 Android 样片决定过滤阈值和 demo 可用性。 |

## 依赖顺序

1. M0：锁定并记录当前 PC-only baseline。
2. M2a：在 PC 离线实现并验证 SceneGate baseline。
3. M1：让 PC 可以启动、停止和监控 Android 摄像头服务。
4. M2b：将已验证的 SceneGate baseline 迁移到 Android，并接入 HTTP 片段上传。
5. M3：接入 PC 片段接收、预览帧标定和 `android_clip` 测速分析。
6. M4：用真实 Android 样片验证过滤策略并加固 demo。

## 里程碑总览

| 里程碑 | 状态 | 目的 |
| --- | --- | --- |
| M0 Current Baseline | Done | 当前 PC-only Web/Backend/OpenCV 闭环已可工作。 |
| M2a PC Offline SceneGate | In Progress | 当前 P0：用 manual_scene 指标评估 PC 离线 baseline，并推进模型辅助 SceneGate spike。 |
| M1 PC Controls Android | Next | PC 管理 Android 服务生命周期和采集状态。 |
| M2b Android Timeline Filtering | Todo | 将 PC 验证过的场景过滤迁移到 Android，在上传前降低数据量。 |
| M3 PC Calibration + Speed Analysis | Todo | PC 将 Android 片段转成标定后的测速结果。 |
| M4 Validation + Demo Hardening | Todo | 用真实样片决定过滤阈值和 demo 可用性。 |

## M0 Current Baseline

**状态：** Done

**目标：** 在引入 Android 前，保留并说明当前已经能工作的 PC baseline。

**已完成：**

- FastAPI 服务提供 session REST API 和 WebSocket 更新。
- 后端支持本地视频文件路径和本地摄像头索引。
- 已实现四点场地标定和平面投影。
- OpenCV motion baseline 可生成轨迹点、速度样本、速度平滑和 speed-spike keyframe event。
- 分析结果可导出 JSON 和 CSV。
- PC Web 可创建 session、输入标定坐标、启动分析、接收 WebSocket 速度样本、展示当前速度和峰值速度。

**完成证据：**

- 代码路径：`backend/app/api/`、`backend/app/vision/`、`backend/app/session_store.py`、`frontend/src/App.tsx`。
- 验证命令：`pnpm run test:backend`、`pnpm run typecheck:frontend`。

**当前缺口：**

- 没有 Android app/service。
- 没有网络 ADB 控制。
- 没有 Android 片段上传链路。
- SceneGate / SceneSegment 已有 PC 离线 baseline，但尚未接入现有测速分析流程。
- 没有 `android_clip` 输入源。
- PC 标定 UI 仍是手动坐标输入，不是预览帧点击标定。
- 没有整理好的 Android 高帧率验证样片。

## M2a PC Offline SceneGate

**状态：** In Progress

**优先级：** P0

**目标：** 先在 PC 上解决场景识别的最小闭环：输入一段视频，输出 `idle` / `rally` 主时间线分段 JSON，并在 `rally` 内输出 `smash_candidate` 候选区间，用少量样片验证它能减少数据量且不明显漏掉杀球候选。

**执行原则：**

- 先 PC 离线验证，不直接做 Android 正式移植。
- 先做时间线分层，不做完整回合开始/结束理解。
- `smash_candidate` 是 `rally` 内部的一段候选时间，不作为与 `rally` 平级互斥的主时间线类别。
- `smash_candidate` 召回优先，宁可多报，不要漏掉，但片段必须达到秒级可复核长度，避免毫秒级碎片。
- 阈值全部可配置，真实样片验证前不写成最终结论。

**任务：**

- 定义 `SceneSegment` / `SceneCandidate` 契约，至少包含 `category`、`start_ms`、`end_ms`、`confidence`、`reason`、`source_frame_range`。（Done）
- 固定第一版主时间线类别：`idle`、`rally`；候选区间类别：`smash_candidate`。（Done）
- 在后端新增 PC 离线 scene gate 模块，先读取本地视频文件。（Done）
- 实现低成本 baseline：ROI 灰度帧差、运动像素比例、连通区域面积、短窗口运动能量峰值、遮挡抑制、秒级片段平滑、最小时长过滤。（Done）
- 新增 manual_scene 自动评估：解析人工 `rally` 区间，计算 precision、recall、F1、hit rate、漏检和误报区间。（Done）
- 实现状态策略：连续低运动标记 `idle`，持续中等运动标记 `rally`，短窗口运动峰值或高速小目标候选标记为嵌套 `smash_candidate`。
- 对开源模型做离线 spike：优先 SoloShuttlePose；若跑不通或效果不佳，再拆 TrackNetV3 + hitting-event detector；所有输出统一转成 `SceneSegment` 区间后用同一评估脚本比较。
- 输出场景识别 JSON，暂时不要求真实裁剪视频文件。（Done）
- 接入现有分析流程的前置步骤：可以先跑 scene gate，再只对 `smash_candidate` 时间范围跑或标记测速候选。
- 准备 3-5 段最小验证样片，并人工记录 `idle` / `rally` / `smash` 大致区间。（已有 `test001.mp4`，待补更多样片）
- 记录验证表：视频名、人工 smash 区间、算法命中区间、是否漏检、保留视频比例。（`test001` 模板已生成，待人工填写）

**完成标准：**

- 给定本地视频文件，可以生成包含 `idle` / `rally` 主时间线和嵌套 `smash_candidate` 候选区间的场景 JSON。
- 3-5 段样片上没有明显漏掉人工标记的杀球候选。
- 能输出保留比例，说明相比全量视频预计能减少多少数据。
- 文档记录当前阈值、失败案例和下一轮调参方向。

**完成后需要补的证据：**

- Scene gate 契约代码路径：`backend/app/models.py` 的 `SceneSegment`、`SceneCandidate`、`SceneGateResult`。
- PC 离线 scene gate 模块路径：`backend/app/vision/scene_gate.py`。
- SoloShuttlePose adapter 路径：`backend/app/vision/soloshuttlepose_adapter.py`。
- 自动化启动脚本：`backend/tests/scene_gate/run_test001.py`。
- SoloShuttlePose spike 脚本：`backend/tests/scene_gate/run_soloshuttlepose_test001.py`。
- manual_scene 评估脚本：`backend/tests/scene_gate/evaluate_manual_scene.py`。
- 流程说明：`backend/tests/scene_gate/README.md`。
- 运行命令：`.venv/bin/python backend/tests/scene_gate/run_test001.py`。
- 单独评估命令：`.venv/bin/python backend/tests/scene_gate/evaluate_manual_scene.py`。
- SoloShuttlePose spike 命令：`.venv/bin/python backend/tests/scene_gate/run_soloshuttlepose_test001.py`。
- 示例 scene gate JSON：`data/exports/scene_gate/test001_scene_gate.json`。
- 最小验证模板：`data/exports/scene_gate/test001_validation_template.md`。
- manual_scene 评估输出：`data/exports/scene_gate/test001_scene_gate_eval.json`、`data/exports/scene_gate/test001_scene_gate_eval.md`。
- 当前 `test001` 运行结果：视频约 309.19s，分析 1853 / 9269 帧，输出 23 个主时间线 segments，其中 `idle` 11 段、`rally` 12 段；嵌套 `smash_candidate` 16 段；最短主片段约 3.50s；`rally` 保留比例 48.93%，`smash_candidate` 比例 15.00%。
- manual_scene 自动评估结果：人工 `rally` 26 段、120.00s；当前 motion baseline precision 55.50%、recall 57.36%、F1 56.42%、manual hit rate 65.38%，说明纯 motion baseline 不足以作为主算法。
- SoloShuttlePose adapter 当前可解析上游 `VideoClip` 产物：`res/videos/<video>/<video>_<begin>-<end>.mp4`，结合同目录视频 metadata 的 `fps` 将帧区间转为 `SceneSegment` rally 区间；验证覆盖见 `backend/tests/test_soloshuttlepose_adapter.py`。
- SoloShuttlePose 外部仓库当前已从 `~/Downloads/SoloShuttlePose-main.zip` 解压到 `models/SoloShuttlePose`，并确认 `main.py` 存在；四个 runtime 权重已从 `~/Downloads/weights-20260507T110316Z-3-001.zip` 安装到 `models/SoloShuttlePose/src/models/weights`。
- SoloShuttlePose 当前 spike 状态：`run_failed`。环境检查已 ready，权重均存在；CPU run 在 `test001` 上 court 预处理扫到 9250 / 9269 帧后输出 `Fail to pre-process`，未生成 `VideoClip` rally mp4，随后为节省资源在 net 预处理 1015 帧处终止。证据见 `data/exports/scene_gate/soloshuttlepose/test001/spike_report.md`、`artifact_manifest.json`、`logs/stdout.log`。
- 测试命令：`pnpm run test:backend`，当前 15 passed。

**当前缺口：**

- `test001_scene_gate_eval.md` 已自动列出漏检和误报区间，但仍需要人工观看视频判断问题来源。
- 当前 motion baseline 与 manual_scene 差距较大，不能继续只靠阈值调参作为主方向。
- SoloShuttlePose 已不再是“只缺权重”的阻塞项；它在 `test001` 上未能通过上游 court 预处理。继续投入前，需要先人工判断是否有可行 reference-frame / crop 方案，否则转向 TrackNetV3 + hitting-event detector 或更轻量的场地/人/球组合 baseline。
- 当前只有 1 段样片，仍需补齐 3-5 段最小验证样片。
- `test001` 默认 ROI 仍是人工粗设，仍需结合人工复核确认是否过窄或过宽。
- 场地内人员遮挡目前只做大前景运动抑制，仍可能误伤近景正常击球或漏掉慢速遮挡。
- SceneGate 结果尚未接入现有测速分析前置流程。

**当前不做：**

- 不做 Android 端正式移植。
- 不做完整回合开始/结束识别。
- 不做模型训练。
- 不做最终杀球动作分类。
- 不把原始素材丢弃策略定型。

## M1 PC Controls Android

**状态：** Next

**目标：** 让 Android 成为可被 PC 远程控制的智能摄像头节点。

**任务：**

- 新增一个无业务 UI 的 Android service。
- PC 通过网络 ADB 完成 bootstrap：发现/连接设备、安装或启动 service、停止 service。
- Android service 启动后主动连接 PC WebSocket。
- 定义运行时控制事件：`start_capture`、`stop_capture`、`update_capture_config`、`ping`。
- 定义状态事件：`device_state`、`capture_state`、`camera_capabilities`、`error`。
- PC 后端新增设备注册表和 WebSocket 控制路由。
- PC Web 新增设备面板，展示连接状态、服务状态、相机能力和采集状态。

**完成标准：**

- 维护者可以从 PC 启动 Android service，在 PC Web 看到心跳/状态，开始采集，停止采集，并停止 service。
- 在无线 ADB 可用后，Android 不需要业务 UI 交互。

**完成后需要补的证据：**

- Android service 路径。
- 后端设备控制路径。
- PC Web 设备面板路径。
- 网络 ADB 启动的 demo 命令或脚本。

**当前缺口：**

- 需要确定 Android project layout。
- 需要实现 service 生命周期。
- 需要 PC 侧 ADB wrapper 和设备状态模型。

## M2b Android Timeline Filtering

**状态：** Todo

**目标：** 将 M2a 在 PC 上验证过的 SceneGate baseline 迁移到 Android，降低回传数据量，同时保留测速和后续视频剪辑需要的素材。

**时间线和候选类别：**

- `idle`：无效非运动场景。直接丢弃，或只保留低频 metadata/log。
- `rally`：普通运动回合。保留低帧率压缩视频，用于后续剪辑。
- `smash_candidate`：`rally` 内部的疑似杀球或高速事件候选区间。额外保留高帧率前后片段，用于测速和慢动作输出。

**baseline 任务：**

- 以 M2a 的 `SceneSegment` / `SceneCandidate` 契约为输入，不重新发明 Android-only 数据结构。
- Android 维护高帧率 ring buffer。
- 将帧降采样为低分辨率灰度图，用于低成本过滤。
- 计算可配置运动特征：帧差、背景差分、运动像素比例、连通区域面积、短窗口运动能量。
- 加入状态窗口和冷却时间，避免单帧噪声产生过多片段。
- 对每个保留片段发出 `scene_gate_event` metadata。
- 通过 HTTP 分片或 multipart 上传保留片段和 manifest 到 PC。

**完成标准：**

- Android 可以持续采集，同时只上传被保留的片段。
- Android 输出的场景分段与 PC 离线 baseline 在同一批样片上可对比。
- PC 收到足够 metadata：片段类别、时间范围、fps、codec、分辨率、触发原因和置信度。
- 过滤策略可由 PC 配置；阈值在 M4 验证前都不是最终结论。

**完成后需要补的证据：**

- Android ring buffer 和过滤代码路径。
- 上传接口路径。
- 示例 uploaded manifest。
- 相比全量高帧率上传的数据量对比样例。

**当前缺口：**

- 没有 Android 采集 pipeline。
- 没有 clip manifest type。
- 没有 mobile upload endpoint。
- 需要先完成 M2a PC 离线 baseline。
- 没有真实样片用于调参。

## M3 PC Calibration + Speed Analysis

**状态：** Todo

**目标：** 在 PC 上把 Android 上传片段转成完成标定的测速结果。

**任务：**

- 新增 `POST /api/mobile/clips` 接收片段文件和 manifest。
- 将上传片段保存到本地数据目录，并保留 source reference 和类别 metadata。
- 新增 `android_clip` analysis source type。
- 从上传片段抽取预览帧，用于 PC 侧标定。
- 在 PC Web 中用点击式四点标定替代或补充当前手动坐标输入。
- 复用现有 OpenCV pipeline 分析 `android_clip` source。
- PC Web 展示速度曲线、峰值、轨迹、关键帧、片段 metadata 和导出路径。

**完成标准：**

- Android 上传一个 `smash_candidate` 片段。
- PC Web 可以选择或打开该片段，在预览帧上完成四点标定，运行分析，并展示/导出结果。

**完成后需要补的证据：**

- 上传和存储代码路径。
- `android_clip` model/API 路径。
- PC 预览帧标定 UI 路径。
- 一次成功端到端片段分析结果路径。

**当前缺口：**

- 当前 `SourceType` 只支持 `video_file` 和 `camera`。
- 当前标定 UI 只有数字输入。
- Session store 没有追踪移动端片段资产和 manifest。

## M4 Validation + Demo Hardening

**状态：** Todo

**目标：** 用真实 Android 片段决定过滤策略，并让 demo 稳定可演示。

**任务：**

- 收集 5-10 段 Android 高帧率样片。
- 人工标注时间线区间：`idle`、`rally`、`smash`。
- 记录无效场景丢弃率、普通回合剪辑质量、杀球召回率、上传数据节省比例、分析耗时和测速结果可信度。
- 调整 Android 阈值、pre-roll/post-roll 长度、冷却时间、压缩设置和重试行为。
- 补齐设备断连、上传失败、manifest 错误、标定失败、无测速结果等失败状态和日志。
- 编写 demo runbook，覆盖 PC 启动、无线 ADB 设置、service 启动、采集、上传、标定、分析和导出。

**完成标准：**

- 新维护者可以按 runbook 跑通 demo。
- 样片验证结果能说明当前 Android 过滤策略为什么可接受，或还剩哪些 TODO。
- 未经验证的算法选择不会被写成最终结论。

**完成后需要补的证据：**

- 样片清单和标签。
- 验证结果表。
- Demo runbook 路径。
- 已知失败列表和下一轮改进项。

**当前缺口：**

- 没有样片清单。
- 没有验证标签。
- 没有 demo runbook。
- 没有量化过滤指标。

## 当前接口目标

这些是 demo 阶段的目标契约。实现早期可以按代码压力调整。

### WebSocket Control

PC to Android:

- `start_capture`
- `stop_capture`
- `update_capture_config`
- `ping`

Android to PC:

- `device_state`
- `capture_state`
- `camera_capabilities`
- `scene_gate_event`
- `upload_state`
- `error`

### HTTP Clip Upload

目标接口：

- `POST /api/mobile/clips`

目标 manifest 字段：

- `device_id`
- `clip_id`
- `timeline_category`: `idle` or `rally`
- `candidate_category`: optional `smash_candidate`
- `start_timestamp_ms`
- `end_timestamp_ms`
- `fps`
- `width`
- `height`
- `codec`
- `pre_roll_ms`
- `post_roll_ms`
- `gate_reason`
- `confidence`

### Analysis Source

目标 source type：

- `android_clip`

PC 后端应该将上传片段保存成本地 source，再把本地路径传入测速 pipeline；不要要求 Android 保留或暴露 PC 可读取的文件路径。

## 维护清单

代码变更落地时：

- 更新对应里程碑状态。
- 给新增 `Done` 任务补充证据。
- 将新发现的问题写入 `当前缺口`。
- Android 算法参数在 M4 验证前都保持 tentative。
- 只有模块边界或数据流变化时，才更新 `docs/architecture.md`。
