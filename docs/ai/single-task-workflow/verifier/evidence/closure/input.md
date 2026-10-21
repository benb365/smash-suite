# 交付收束机械检查

本轮只做已授权文档构建与差异格式检查，不读取真实 developer/，不修改实现、标准、依赖或链接，不提交/合入/推送。

1. 任务 worktree：/Users/bytedance/.codex/worktrees/single-task-workflow/smash-suite。
2. 在 tools/docs-site 目录使用现有 Node/依赖运行 `node node_modules/vitepress/bin/vitepress.js build`，收集确切命令、目录、退出状态及关键输出。如 sandbox 不允许生成缓存，按已批准构建范围申请该命令 escalation。不得安装、更改锁文件、请求 registry 或放宽策略；不重跑 pnpm 入口。
3. 在任务 worktree 执行 `git diff --check`，收集结果。
4. 不做新的产品测试或演练。只将实际结果写本目录 output.md；未执行如实记录。结束通知只给该 output.md 绝对路径。
