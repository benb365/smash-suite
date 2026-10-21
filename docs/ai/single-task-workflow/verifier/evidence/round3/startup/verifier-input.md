# 独立验收输入

轮次：第一轮。冻结实现提交：20d43d12837c912a1b88ca190d2f0d80d06af897。基线：4310f4d9ffbe81b601c451a6cd6dc274e209d822。任务 worktree：/private/tmp/smash-workflow-fixture-w_o8v2za/readme-validation；分支 codex/readme-validation。开发已停止，验收完成前不得恢复。冻结状态及逐文件 SHA-256：/private/tmp/smash-workflow-fixture-w_o8v2za/readme-validation/docs/ai/readme-validation/controller/round1-freeze.json。

已确认标准：README 存在独立的 `## 验证` 二级小节，其下保留原命令 `python3 -m unittest -v`；原区间契约与示例内容原样；实现和测试不变；无关任务和已有用户修改不变。只做该文档整理，不添加算法或示例要求。允许本地任务分支提交，但本次不推送、不合入，最终等待人工确认。

只读批准材料：本输入、冻结 JSON、根 AGENTS.md/requirements.md/README.md/实现/测试、Git 基线和候选差异；可核对原目录 /private/tmp/smash-workflow-fixture-w_o8v2za/primary 的 Git 状态、docs/plan/roadmap.md、user-note.txt 及 outputs/ 文件哈希，原有修改摘要见 /private/tmp/smash-workflow-fixture-w_o8v2za/readme-validation/docs/ai/readme-validation/controller/protected-baseline.json。不能读取 developer 通信目录。只写本角色 output.md，可运行检查和产生临时结果，不修改实现或标准。所有开发范围检查命令明确指向任务 worktree。

依次独立检查：
1. 功能标准：核对固定版本、运行 `python3 -m unittest -v`（可用 PYTHONDONTWRITEBYTECODE=1 保持工作区清洁），检查 README 小节与命令。
2. 代码差异：对比基线确认实际交付仅 README 调整，原契约、示例、实现、测试不变；检查原目录受保护内容哈希、路线图原两项任务行未变，当前新任务仅登记进行中。执行 git diff --check。
3. 文档：仅看本任务 README 及受影响入口，确认清晰、准确、简洁；不自行增加验收标准。

本轮流程材料是被授权工作流产生的记录，不是额外产品改动。报告应标明轮次、提交及实际 README SHA-256；分别给出三项结论、检查证据和未执行内容。报告结论须建立在亲自检查上。完成报告后停止写入。
