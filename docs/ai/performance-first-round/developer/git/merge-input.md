# 已批准首轮优化进入 develop（暂停在待提交状态）

轮次 integration-merge-1。主目录 `/Users/bytedance/workspace/experiments/smash-suite` 的develop应仍为 `5c946e9e6186d052624ca6f853a62d40f034f6e8`。任务分支 `codex/performance-first-round` 的最新本地提交已包含独立验收通过的OPT03/04代码。用户已明确允许把实际优化代码及本轮全部结果/报告合入develop，不授权push。主控随后负责状态文档更新与集成验证；本次只做机械Git，不读开发/验收通信正文。

## 保留主目录修改

合入前主目录已有未提交的旧规划：docs/README.md、docs/plan/roadmap.md、docs/features/performance-optimization/README.md、docs/features/performance-optimization/first-round.md。已核对属于同一任务旧规划，任务分支包含其现行方案、入口和报告。仍先完整保存这四个重叠路径，禁止直接覆盖。ideas.md 和 outputs/ 不在本次集成提交范围；outputs/ 不读取/修改。ideas SHA必须始终为 `5f0066e40861792a09d79324602ad890ece794fc585534ce8bc8093f3c23bba5`。

## 操作

1. 核对主分支、HEAD、无已有staged改动或合并状态。检查任务提交已完成；如有异常停止。
2. 用路径限定的 `git stash push --include-untracked` 保存且只保存上述四个重叠文件，message为 `codex-performance-first-round-overlap-20261021`。记录新stash准确SHA和路径清单；不要pop/drop。确保ideas未变、outputs未加入stash，本次新建 docs/ai/.../developer/git/merge-input.md 也留在主目录，不能一并stash。
3. `git merge --no-ff --no-commit codex/performance-first-round`。遇冲突只报告，不擅自解决、不reset。成功后保持待提交合并状态。
4. 输出准确目标分支SHA、stashSHA、merge状态和git status摘要。在 docs/ai/performance-first-round/developer/git/merge-output.md 保存动作/结果；不要提交此待合并状态，不修改任何产品实现或文档，不push、不归档worktree。
