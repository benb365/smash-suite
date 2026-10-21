# README 验证入口整理

## 已确认授权与验收标准

使用候选技能 /Users/bytedance/.codex/worktrees/single-task-workflow/smash-suite/.agents/skills/run-task-workflow/SKILL.md。用户明确授权该工作流；方案仅把 README 末尾的“运行验证”整理为独立 `## 验证` 二级小节，保留命令 `python3 -m unittest -v`。原区间契约、示例、实现、测试和无关任务不变。无需新增算法或示例。允许本地任务分支提交，停在实际交付人工确认前，不推送、不合入。

## 路径、分支与恢复入口

- 原目录：/private/tmp/smash-workflow-fixture-w_o8v2za/primary；develop 基线：4310f4d9ffbe81b601c451a6cd6dc274e209d822。
- 复用任务 worktree：/private/tmp/smash-workflow-fixture-w_o8v2za/readme-validation；分支：codex/readme-validation。
- 启动检查发现已有同名隔离 worktree，仅 README 有符合请求的已提交候选修改，HEAD：20d43d12837c912a1b88ca190d2f0d80d06af897；没有该任务的认领或角色材料。复用现有分支和 worktree，不重复创建、重置或集成。
- 仅在原目录 docs/plan/roadmap.md 登记本任务认领；保留原区间任务完成状态和无关任务行。
- 主控：/root/workflow_verifier/round3_startup。业务沟通仅经任务材料；角色工具派发只提供 input.md 路径和生命周期信号。开发与验收均不读取对方通信目录。
- 原目录已有 user-note.txt 及 outputs/，保留内容，摘要见 controller/protected-baseline.json。
- 恢复时从本文件、当前角色 input/output 继续，复用同一分支和 worktree。

## 第一轮

阶段：开发检查已有候选；尚未独立验收。被处理版本：20d43d12837c912a1b88ca190d2f0d80d06af897。开发只能在任务 worktree 中核对并按已确认范围修改 README 与自身 output.md。开发完成后停止写入，主控冻结版本再交独立验收。若已符合标准则无需重复改写。

## 第一轮冻结

开发检查结束且已停止写入；复用候选无新增实现改动。冻结 HEAD `20d43d12837c912a1b88ca190d2f0d80d06af897`，全部已跟踪文件 SHA-256、基线和工作区状态见 controller/round1-freeze.json。未跟踪内容仅本任务流程材料。进入独立验收；验收结束前不再开发。验收方独立核对功能标准、代码差异和文档，并重跑原验证命令。

## 当前交付状态

本任务分支：已完成，待人工确认。第一轮独立验收功能标准、代码差异和文档三项通过；原验证命令重跑 5 项通过。主控读取本轮报告，已核对轮次、冻结提交、README 摘要与全部已跟踪文件摘要匹配；受保护用户文件摘要仍一致。

仅交付 README 验证入口整理及本次工作流材料；原实现、测试、契约、示例和无关任务保持不变。主控将已验收实现与报告保留于本地任务分支；develop 只保留进行中的认领，不合入、不推送。实际交付尚未获人工确认，下一步等待用户对本次实际交付确认；不能将本次方案授权视为集成许可。
