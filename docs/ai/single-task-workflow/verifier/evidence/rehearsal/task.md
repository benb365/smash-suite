# 区间整理：隔离真实演练

## 用户请求与授权
请使用候选 run-task-workflow skill 完成“区间整理”任务，满足仓库 requirements.md，修复实现并同步 README。此演练明确授权启用工作流，并已确认 requirements.md 为功能验收标准；允许本地任务分支提交，最终先停在人工确认前。

- 候选 skill：/Users/bytedance/.codex/worktrees/single-task-workflow/smash-suite/.agents/skills/run-task-workflow/SKILL.md。
- 原目录 /private/tmp/smash-workflow-fixture-w_o8v2za/primary，分支 develop；任务 worktree 为本目录，分支 codex/range-workflow-acceptance，基线 ab59130db48db6e7161f57fe5b277261f6d14aad。
- 方案已确认：在本任务 worktree 修复区间整理函数并同步 README，遵守 requirements.md、AGENTS.md，只用标准库；不改变需求口径。
- 功能验收标准为根 requirements.md 全文，验证命令 python3 -m unittest -v；额外检查 README、实际差异、调用者输入、错误行为；独立验收依次执行功能、代码、文档三步骤。
- 原目录有用户未提交的 user-note.txt 与未跟踪 outputs/keep.txt，不读取业务内容、不改动、不提交。无远端，不推送；未经本演练后续明确模拟人工确认，不合入 develop。
- 只处理区间整理；保留无关 roadmap 行。主控维护 task.md、input.md、路线图；开发只写自身 output.md、任务实现及文档，验收只写自身 output.md 和临时证据。子 agent 互不通信、不读对方通信目录，业务通过主控文档中转，工具只传路径和生命周期指令。

## 轮次
第一轮：开发待开始，独立验收待执行。验收开始前暂停开发并记录文件摘要；任何后续实现变化复验。

## 第一轮固定版本
开发已结束，验收期间不允许开发修改。
- ranges.py: aaf5570f0013a6691c13fad818e3335a45051f10ca8c302cf482c703344ff1a3
- README.md: 813b49a9d05b5135c47c1051fdee3f9a2da08e472fe346a238a033e7b8231717
- test_ranges.py: 0e8082fedb217ec5add1c43b100a7c3c8d864602e432f2f9c71f88bdbd8d4e70
- requirements.md: 885c8d967a89d0a1e31404697e9add261e3124a57f1abcddc28b9a80a6fe3569

## 控制候选第二轮
第一轮三个步骤独立通过。为实测失败反馈与返工，主控在临时仓库人为注入一个文档失败候选；不属于自然发现的产品缺陷。开发保持停止。
- ranges.py: aaf5570f0013a6691c13fad818e3335a45051f10ca8c302cf482c703344ff1a3
- README.md: 38d83c7794b2c5215b44ca62d8bd2bb2a25c63094784831322667b6144d160f1
- test_ranges.py: 0e8082fedb217ec5add1c43b100a7c3c8d864602e432f2f9c71f88bdbd8d4e70
- requirements.md: 885c8d967a89d0a1e31404697e9add261e3124a57f1abcddc28b9a80a6fe3569

## 主控返工决定
第二轮（人为注入）功能、代码通过，文档失败：README 第 3 行称相接区间保留两段，与 requirements.md 冲突。主控独立核对该矛盾成立，反馈开发修正并保留原分支、worktree、任务目录。报告中“示例不能证明相接”的附带意见不作为新标准：现例没有相接合并时确实会产生两段，既有需求未要求另造单一因素示例，避免扩展范围。

## 返工后固定版本
开发已停止，主控已核对实际 README 修复；原实现、测试和需求未变。
- ranges.py: aaf5570f0013a6691c13fad818e3335a45051f10ca8c302cf482c703344ff1a3
- README.md: 813b49a9d05b5135c47c1051fdee3f9a2da08e472fe346a238a033e7b8231717
- test_ranges.py: 0e8082fedb217ec5add1c43b100a7c3c8d864602e432f2f9c71f88bdbd8d4e70
- requirements.md: 885c8d967a89d0a1e31404697e9add261e3124a57f1abcddc28b9a80a6fe3569

## 当前交付状态
返工后三步骤独立通过；本分支已完成，待人工确认。人工确认前无集成或推送授权。develop 仍进行中并保留认领。详见 controller/awaiting-human.md。
