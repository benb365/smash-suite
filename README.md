# Smash Suite

Smash Suite 的首个产品是独立打包的本机网页视频剪辑应用：浏览器访问本机地址，选择拍摄类型和 MP4，自动识别并生成带原声音的精简 MP4，预览成片后通过系统窗口保存。界面使用 ReactLynx + Lynx for Web；首版不含时间轴编辑、历史记录或 Android 采集接入。算法改进与产品开发并行。

## 运行本机测试包

完整解压 `dist/SmashSuite-macos-arm64.zip`，运行文件夹中的 `smash-suite`。程序会打开 `http://127.0.0.1:18780/`；请使用 Chrome 或 Edge。运行时不需要本仓库、Python 或 Node，文件夹中的配套资源需要一起保留。

首次识别需要联网下载模型，之后复用缓存并可离线处理。操作步骤与临时文件清理规则见[使用说明](docs/product-usage.txt)。首包面向 macOS Apple 芯片本机测试，尚未签名和公证。

## 流式算法输入契约

流式回合分割器消费时间戳单调递增的视频帧，并在确认回合结束后输出该回合的完整时间区间：

```text
TimestampedFrame(frame_id, timestamp_ms, image)
  ──► streaming rally segmenter
  ──► RallyInterval(rally_id, start_ms, end_ms, emitted_at_ms)
```

该流式分割器在线处理当前帧和历史状态，不读取未来帧。它可以在内部回溯候选开始点，但只在结束确认后一次性输出完整区间。首版文件剪辑产品中的场边低视角、个人斜侧方方案使用离线上下文，不属于上述流式契约。

## 当前状态

项目正在实测回合分割算法，正式内部架构尚未选型。新增的 TrackNet
候选已跑完现有样片，提供可重现命令、逐回合时间列表和轨迹视频，见
[实测报告](docs/experiments/tracknet-rally-segmentation.md)。当前优先级与
后续任务只维护在[路线图](docs/plan/roadmap.md)。

旧球速应用保存在 `backup/`。首版产品复用 `backend/app/algorithms/` 中记录来源与配置的冻结算法，运行时不读取实验目录、人工标注或实验缓存；后续实验不会自动替换产品算法。

## 范围

本阶段包括：

- 固定流式帧输入和完整回合区间输出契约；
- 建立数据集清单、人工标注格式和统一评估器；
- 用同一 benchmark 比较不同算法路线；
- 依据 benchmark 选择并实现正式路线。
- 开发视频输入、自动识别与成片预览、带原音频的连续MP4导出；产品接手范围见[任务说明](docs/plan/video-clipping-product-task.md)。

本地视频 replay 只是验证适配器，不是正式输入协议。

## Seed benchmark

现有 `datasets/badminton-v1/local/ysp/test_ysp.ts`、关联 ROI 和 verified 人工回合标注继续作为第一份 benchmark 数据。旧 trace、参数和效果结论不继承。在收集更多样片前，只建立可复现 baseline，不制定数值通过阈值。

## 顶层目录与数据归属

顶层目录已按下列职责归位，运行命令已更新。datasets/local 内部清理与重整尚未完成，
当前进度以[路线图](docs/plan/roadmap.md)为准；文件对应关系见[迁移记录](docs/experiments/top-level-migration-20261014.json)。

| 目录 | 职责 |
| --- | --- |
| `backend/` | 后端与视频分析代码及测试；保留目录结构，仅调整必要路径 |
| `frontend/` | ReactLynx 本机网页；Android采集工程独立保留 |
| `backup/` | 历史归档及已移出的旧球速应用 |
| `datasets/` | 测试视频、人工标注、素材来源和测试集清单 |
| `models/` | 各模型的实现、权重、参数配置及模型运行中间数据 |
| `tools/` | 独立工具，包括浏览器采集插件 |
| `docs/` | 当前维护的产品、系统、路线图、评估和实验文档 |
| `.agents/` | 代理任务流程、规则及其配套脚本；仓库技能的唯一维护位置 |

已取消顶层 `captures/` 和 `data/`：采集工具归 `tools/`，测试输入统一归 `datasets/`。
实验识别结果放在对应模型目录中。缓存和运行中间数据排除 Git 管理，
已有历史实验记录保留，不能作为临时缓存清理。技能自带脚本继续随技能存放。

产品运行目录独立于仓库；模型缓存与随页面会话清理的临时工作分开，默认位于应用自己的用户数据目录。TrackNet、YOLO 实验产物仍位于对应模型目录的 `.runtime/`。

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
- [首个视频剪辑产品：新会话任务说明](docs/plan/video-clipping-product-task.md)
- [需求与评估口径](docs/plan/rally-segmentation-requirement.md)
- [视频结果查看skill](.agents/skills/review-video-results/SKILL.md)
- [轨迹方向、高球连接与回击候选试验](docs/experiments/m1-a-trajectory-20261016.md)
- [给球与短片段过滤对照](docs/experiments/m1-a-return-filter-20261016.md)
- [给球过滤参数复查](docs/experiments/m1-a-return-threshold-20261016.md)
- [C1场边低视角过滤检查](docs/experiments/m1-c1-filter-check-20261017.md)
- [C1/D1优化检查与现有参数取舍](docs/experiments/m1-cd-optimization-20261017.md)
- [C1/D1坐标规则优化、逐回合损失与可复现参数](docs/experiments/m1-cd-coordinate-20261017.md)
- [文档与 Agent 入口](docs/README.md)

历史文档已隔离在 `backup/docs/`，只用于追溯，不能指导当前开发。

## 仓库状态说明

旧球速页面及其专用后端已移至 `backup/legacy-speed-20261018/`；当前 `frontend/` 和应用入口服务于本机剪辑产品。算法候选的存在不等于正式选型；产品实施与验收证据只维护在路线图。
