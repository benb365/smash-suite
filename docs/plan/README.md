# Smash Suite 计划手册

`docs/plan/` 是 Smash Suite 的作战手册目录，用来回答当前应该先做什么、做到哪里、缺什么证据、被什么阻塞。

## 文件职责

- `docs/plan/roadmap.md`：唯一的当前优先级、里程碑状态、完成标准、证据、阻塞和下一步工作来源。
- `docs/plan/README.md`：计划维护规则、状态枚举和路线图更新规范。

不要把当前任务状态复制到 `AGENTS.md`、`docs/README.md`、`docs/features.md` 或 `docs/architecture.md`。这些文档可以链接 roadmap，但不承担当前进度记录。

## 使用方式

1. 从 `docs/plan/roadmap.md` 顶部的 `Current Focus` 判断当前最高优先级任务。
2. 如果 `Current Focus` 与代码不一致，先用代码事实修正 roadmap。
3. 实施任务时只更新对应里程碑的状态、证据、缺口和阻塞。
4. 只有产品范围变化时才更新 `docs/features.md`。
5. 只有职责边界、数据流、传输方式、存储策略或契约变化时才更新 `docs/architecture.md`。

## 状态枚举

- `Done`：已实现，并有证据。
- `In Progress`：部分实现，或正在推进。
- `Next`：下一步计划做。
- `Todo`：计划中，尚未开始。
- `Blocked`：被决策、依赖或数据阻塞。
- `Deferred`：有意延后。

## 优先级规则

- `P0` 是当前最高优先级。
- 同一优先级内，先继续 `In Progress`，再开始 `Next`，最后才处理 `Todo`。
- `Blocked` 项必须写清阻塞原因和解除阻塞所需的最小下一步。
- 不要因为高优先级任务较难，就静默跳到低优先级功能。

## 证据要求

每个 `Done` 项都需要至少一种证据：

- 代码路径。
- 测试命令和结果。
- demo 脚本或运行命令。
- 示例输出、导出文件、样片清单或验证表。

证据应写在对应里程碑中，不放在本文件。

## 维护清单

代码或文档变更落地时：

- 更新 `docs/plan/roadmap.md` 的 `Current Focus` 或对应里程碑。
- 给新增 `Done` 任务补充证据。
- 将新发现的问题写入 `当前缺口` 或 `Blocked` 原因。
- Android 算法参数在真实样片验证前都保持 tentative。
- 始终保持 Android/PC 边界清晰：Android 降数据量；PC 负责标定、分析、结果和产品 UI。
