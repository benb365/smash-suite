# 独立静态与文档构建证据

## 已执行

- `/Users/bytedance/workspace/experiments/smash-suite/.venv/bin/python /Users/bytedance/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/run-task-workflow`：exit 0，`Skill is valid!`。
- `git diff --check`：exit 0，无错误。
- 本地 `codex app-server --stdio` 的 initialize → skills/list（cwds 指向任务 worktree，forceReload=true），完成后退出；得到 name=run-task-workflow、scope=repo、enabled=true、path 指向候选 SKILL.md。未启动模型或任务。第一次 sandbox 内无法初始化本地 sqlite；按已授权范围 escalation 后通过。
- `pnpm run docs:build`：exit 1。运行前依赖策略检查失败，ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION：watchpack@2.6.3 不在 registry manifest；未执行到 VitePress。没有安装、更改锁文件或放宽策略。
- 读取根 package.json 和 tools/docs-site/package.json，确认实际构建为 vitepress build；在 tools/docs-site 运行 `node node_modules/vitepress/bin/vitepress.js build`：exit 0，VitePress 1.6.4，`build complete in 7.50s`。仅 chunk >500 kB 警告；复用已安装 Node/依赖。
- 产物检查：59 个 HTML 页面，无 docs/ai/、AGENTS.html 或 .agents/ skill 页面。配置明确排除 docs/ai/**、AGENTS.md；执行日志未进入阅读章节。
- 对比基线，roadmap 除两个自动协作 workflow 行外逐行相同；性能/Windows 负责人、其余任务、优先级与斜体未变。README、docs/README、tools/docs-site/README 未改。

## 适用范围

本轮仅规则和文档，没有产品改动；产品测试不要求。文档构建本身通过，但 `pnpm run docs:build` 这个入口在现有 registry/策略环境下仍受阻，不能把入口命令说成通过。
