# 开发输入

轮次：第一轮。被处理实现版本：20d43d12837c912a1b88ca190d2f0d80d06af897，基线 4310f4d9ffbe81b601c451a6cd6dc274e209d822。任务 worktree：/private/tmp/smash-workflow-fixture-w_o8v2za/readme-validation；分支 codex/readme-validation。

用户已经确认且只授权：README 末尾把现有“运行验证”整理为独立 `## 验证` 小节，小节内保留 `python3 -m unittest -v`。原区间契约、示例、实现和测试不变；不新增算法或示例要求，不改无关任务及已有用户修改。此处已有候选提交，核对符合标准即交付，无需为产生新差异而改写。

可只读：本输入、/private/tmp/smash-workflow-fixture-w_o8v2za/readme-validation/AGENTS.md、/private/tmp/smash-workflow-fixture-w_o8v2za/readme-validation/README.md、/private/tmp/smash-workflow-fixture-w_o8v2za/readme-validation/requirements.md、基线与候选 Git 差异。禁止读取 verifier 通信目录。只可写本角色 output.md 与本任务 README，不能改 task.md、路线图、验收输入或标准，不能提交、推送、合入。所有命令明确在上述 worktree 执行。

核对 README、候选与基线差异，确认仅文档入口变化；必要时做符合已授权范围的最小修改。执行 git diff --check；若重跑原验证命令则准确记录。角色输出标明轮次、提交、实际文件摘要、修改和检查结果。完成输出后停止写入，等待主控。
