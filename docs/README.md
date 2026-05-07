# Smash Suite 文档入口

`docs/` 维护项目的产品目标、架构边界和执行计划。新 agent 不需要从头读完所有文档；先根据任务类型选择最短路径。

## 阅读路径

| 目的 | 阅读顺序 |
| --- | --- |
| 快速接手当前最高优先级任务 | `README.md` -> `AGENTS.md` -> `docs/plan/roadmap.md` 的 `Current Focus` |
| 理解产品范围和非目标 | `README.md` -> `docs/features.md` |
| 理解职责边界、数据流和目标契约 | `README.md` -> `docs/architecture.md` |
| 维护里程碑、状态、证据和阻塞 | `docs/plan/README.md` -> `docs/plan/roadmap.md` |

## 文档职责

| 文档 | 维护内容 | 何时更新 |
| --- | --- | --- |
| `README.md` | 项目简介、当前可跑 baseline、运行方式和快速接手入口。 | 运行方式、目录结构或 baseline 描述变化时。 |
| `AGENTS.md` | agent 快速入口和任务选择规则。 | onboarding 路径或任务选择规则变化时。 |
| `docs/features.md` | 稳定产品目标、功能模块、demo 范围、非目标。 | 产品目标、功能范围、非目标或主要能力边界变化时。 |
| `docs/architecture.md` | 稳定职责边界、数据流、传输方式、存储策略和目标契约。 | 职责边界、数据流、传输方式、存储策略或契约变化时。 |
| `docs/plan/README.md` | 计划维护规则、状态枚举、证据要求和路线图使用方式。 | 计划维护规则或状态定义变化时。 |
| `docs/plan/roadmap.md` | 当前优先级、里程碑状态、完成标准、证据、阻塞和下一步工作。 | 代码能力落地、任务被阻塞、优先级变化或新工作被发现时。 |

## 仓库工作流

- 编辑前先看 `git status --short`。工作树可能包含用户或其他 agent 的未提交改动。
- 保留已有用户工作。除非明确要求，不要 revert、delete、stage、commit 或 push。
- 搜索优先用 `rg` 或 `rg --files`。
- 优先沿用现有项目模式，不为单个任务引入新的抽象风格。
- 实现改动保持在当前任务范围内；代码能力、阻塞或范围变化时，同步更新对应文档。

## 常用检查

```bash
pnpm run test:backend
pnpm run typecheck:frontend
git diff --check
```

只改文档时至少运行 `git diff --check`；没有运行某项检查时，在交付说明里写清原因。

## 交付前

- 确认相关检查已运行，或说明未运行原因。
- 更新 `docs/plan/roadmap.md` 中对应的状态、证据、阻塞或新发现缺口。
- 只有文档职责范围确实变化时，才更新其他文档。
- 总结改动文件和验证结果。

## 维护原则

- `docs/features.md` 和 `docs/architecture.md` 解释稳定边界：我们要做什么，以及系统应该长什么样。
- `docs/plan/roadmap.md` 解释当前执行状态：现在先做什么、做到哪里、还缺什么。
- 当前状态不要复制到多个文档；roadmap 是唯一来源。
- 当前任务状态不要放进 `AGENTS.md`。
- 每个 `Done` 计划项必须有证据：代码路径、测试命令、demo 脚本或验证样片。
- Android 端过滤策略在真实样片验证前保持 tentative，不写成最终结论。
