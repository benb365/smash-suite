# 文档与 Agent 入口

## Agent 入口

仓库规则只维护一份：

- Codex、OpenAI Codex 兼容客户端和读取 `AGENTS.md` 的 Agent：从根目录 `AGENTS.md` 开始。
- Claude Code：从根目录 `CLAUDE.md` 开始；该文件只导入 `AGENTS.md`。
- 其他 Agent：若不会自动识别上述入口，应显式读取 `AGENTS.md`，不要复制规则。

## 主动阅读路径

按任务只读取必要文档：

1. `README.md`：目标、范围、当前状态和入口。
2. `docs/plan/roadmap.md`：当前优先级、状态、证据、阻塞和下一项工作。
3. `docs/features.md`：稳定产品范围与非目标。
4. `docs/architecture.md`：已接受的系统边界和契约；当前内部算法尚未选型。
5. `docs/plan/rally-segmentation-requirement.md`：数据、标注和评估口径。
6. `docs/plan/README.md`：计划文档维护规则。
7. [视频结果展示入口](video-result-review.md)：指向仓库内 `review-video-results` skill；固定查看器、数据格式和展示约定均由 skill 维护。

`backup/docs/` 不属于主动阅读路径。旧代码和归档文档都不能作为当前架构、当前需求或完成状态的证据；明确进行历史追溯时，引用必须标注为“历史假设”。

## 文档职责

| 文档 | 唯一职责 |
| --- | --- |
| `README.md` | 仓库目标、范围、当前状态和导航 |
| `AGENTS.md` | 跨 Agent 的共享执行规则 |
| `CLAUDE.md` | Claude Code 的薄入口 |
| `docs/features.md` | 稳定产品边界与非目标 |
| `docs/architecture.md` | 已接受的系统边界、契约和正式架构 |
| `docs/video-result-review.md` | 视频结果查看 skill 的发现入口 |
| `.agents/skills/review-video-results/` | 固定播放器与时间轴、运行脚本、输入格式和维护检查 |
| `docs/plan/roadmap.md` | 当前优先级、状态、证据、阻塞和下一步 |
| `docs/plan/rally-segmentation-requirement.md` | benchmark 数据、标注和指标定义 |
| `docs/plan/README.md` | 计划文档的维护方法 |
| `backup/docs/README.md` | 历史快照的隔离与引用规则 |

## 更新原则

- 产品边界变化时更新 `docs/features.md`。
- 输入输出契约或被接受的正式架构变化时更新 `docs/architecture.md`。
- 数据、标注或指标口径变化时更新 requirement。
- 视频检查的脚本、模板、输入格式及交互约定只更新 `review-video-results` skill；项目文档保留入口，不复制规则正文。
- 优先级、状态、证据或阻塞变化时更新 roadmap。
- 不把实时状态复制进稳定文档，也不把历史假设重新提升为当前事实。
