# Smash Suite

Smash Suite 当前只解决一个问题：消费时间戳单调递增的羽毛球视频帧，并在确认回合结束后输出该回合的完整时间区间。

```text
TimestampedFrame(frame_id, timestamp_ms, image)
  ──► streaming rally segmenter
  ──► RallyInterval(rally_id, start_ms, end_ms, emitted_at_ms)
```

分割器在线处理当前帧和历史状态，不读取未来帧。它可以在内部回溯候选开始点，但只在结束确认后一次性输出完整区间。

## 当前状态

项目正在实测回合分割算法，正式内部架构尚未选型。新增的 TrackNet
候选已跑完现有样片，提供可重现命令、逐回合时间列表和轨迹视频，见
[实测报告](docs/experiments/tracknet-rally-segmentation.md)。当前优先级与
后续任务只维护在[路线图](docs/plan/roadmap.md)。

仓库中的人物检测、跟踪、脚点运动和状态机代码暂时保留，统一视为 legacy experiment。它们的参数、trace、接口和效果结论不约束新方案；代码清理将在完成 benchmark 和架构选型后单独进行。

## 范围

本阶段包括：

- 固定流式帧输入和完整回合区间输出契约；
- 建立数据集清单、人工标注格式和统一评估器；
- 用同一 benchmark 比较不同算法路线；
- 依据 benchmark 选择并实现正式路线。

本地视频 replay 只是验证适配器，不是正式输入协议。

## Seed benchmark

现有 `datasets/badminton-v1/local/ysp/test_ysp.ts`、关联 ROI 和 verified 人工回合标注继续作为第一份 benchmark 数据。旧 trace、参数和效果结论不继承。在收集更多样片前，只建立可复现 baseline，不制定数值通过阈值。

## 顶层目录与数据归属

顶层目录已按下列职责归位，运行命令已更新。datasets/local 内部清理与重整尚未完成，
当前进度以[路线图](docs/plan/roadmap.md)为准；文件对应关系见[迁移记录](docs/experiments/top-level-migration-20261014.json)。

| 目录 | 职责 |
| --- | --- |
| `backend/` | 后端与视频分析代码及测试；保留目录结构，仅调整必要路径 |
| `frontend/` | 网页应用；保留原样 |
| `backup/` | 历史归档；本轮先不调整 |
| `datasets/` | 测试视频、人工标注、素材来源和测试集清单 |
| `models/` | 各模型的实现、权重、参数配置及模型运行中间数据 |
| `tools/` | 独立工具，包括浏览器采集插件 |
| `docs/` | 当前维护的产品、系统、路线图、评估和实验文档 |
| `.agents/` | 代理任务流程、规则及其配套脚本；仓库技能的唯一维护位置 |

已取消顶层 `captures/` 和 `data/`：采集工具归 `tools/`，测试输入统一归 `datasets/`。
应用任务记录、识别结果和最终导出视频放在与相应应用执行目录相关的相对目录中；
模型参数及其运行中间数据放在对应模型文件夹内。缓存和运行中间数据排除 Git 管理，
已有历史实验记录保留，不能作为临时缓存清理。技能自带脚本继续随技能存放。

后端默认使用执行工作目录下的 `.runtime/` 保存任务和导出数据；项目启动命令在
`backend/` 下运行。TrackNet、YOLO 的运行产物分别位于对应模型目录的 `.runtime/`。

## 文档入口

文件输入和实时模拟实验入口：

```sh
models/SoloShuttlePose/.venv/bin/python backend/tests/rally_benchmark/run_live_tracknet.py \
  --video datasets/badminton-v1/local/ysp/test_ysp.ts --mode realtime --device mps \
  --output models/SoloShuttlePose/.runtime/realtime-seed
```

`--mode offline` 尽快处理；默认实时模式按源 PTS 原速调度，使用已有
TrackNet 权重、不编码预览视频。依赖声明包含 `av==14.2.0`。更多命令、
性能与局限见[输入模块实测](docs/experiments/realtime-input.md)。

- [产品范围](docs/features.md)
- [系统边界](docs/architecture.md)
- [当前路线图](docs/plan/roadmap.md)
- [需求与评估口径](docs/plan/rally-segmentation-requirement.md)
- [视频结果展示约定](docs/video-result-review.md)
- [轨迹方向、高球连接与回击候选试验](docs/experiments/m1-a-trajectory-20261016.md)
- [给球与短片段过滤对照](docs/experiments/m1-a-return-filter-20261016.md)
- [给球过滤参数复查](docs/experiments/m1-a-return-threshold-20261016.md)
- [C1场边低视角过滤检查](docs/experiments/m1-c1-filter-check-20261017.md)
- [C1/D1优化检查与现有参数取舍](docs/experiments/m1-cd-optimization-20261017.md)
- [C1/D1坐标规则优化、逐回合损失与可复现参数](docs/experiments/m1-cd-coordinate-20261017.md)
- [文档与 Agent 入口](docs/README.md)

历史文档已隔离在 `backup/docs/`，只用于追溯，不能指导当前开发。

## 仓库状态说明

现有 `backend/`、`frontend/` 和其他运行代码尚未按新目标整理。除非当前路线图明确要求，不应把它们视为正式架构或继续扩展旧实验。
