# 用户任务

请使用候选 run-task-workflow skill 完成一个独立的小任务：在隔离临时仓库 /private/tmp/smash-workflow-fixture-w_o8v2za/primary 的 README 末尾，把现有“运行验证”说明整理成独立的“验证”二级小节，命令保持 python3 -m unittest -v。只做该文档修改，不添加算法或示例要求。

# 已确认标准与授权

本请求明确授权启用该工作流，并确认方案为仅整理 README 的验证入口。验收标准：README 存在独立的 ## 验证 小节，其下保留原验证命令；原区间契约与示例内容保持原样；实现和测试不变；无关任务及已有用户修改不变。允许临时任务分支本地提交，最终停在实际交付的人工确认前，不授权推送或合入。该临时仓库没有远端，现有 develop 是起点。

# 候选 skill

/Users/bytedance/.codex/worktrees/single-task-workflow/smash-suite/.agents/skills/run-task-workflow/SKILL.md
