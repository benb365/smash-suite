# develop 集成复核

用户已对实际任务提交 3b0ef65b42b40912ab36ef0cf5b7d573ef7e7707 明确回复“同意合入develop 并推送”。本阶段主控已在原目录 /Users/bytedance/workspace/experiments/smash-suite 的 develop，基线 2ccf5f60b7638774aded138a8af00801501a72f2，准备 squash，尚未提交或推送。原独立功能／代码／文档验收已通过；本轮只核对集成状态和内容一致性，不重跑旧演练、不检查新功能。

以独立上下文读取本输入及 task.md、实际源码／文档，必要时读原独立验收报告。不读取 developer/、integration/git/ 或联系其他 agent。只写本目录 output.md，可产生临时验证结果，不改实现、标准、暂存区，不提交／推送。业务通信经本文件，完成通知只给 output.md 绝对路径。

检查：

1. 逐文件对照原已验收提交，除 docs/plan/roadmap.md 和 docs/ai/single-task-workflow/task.md 外，其余已验收文件逐字不变；新增仅 integration/ 通信与交付记录。skill SHA-256 ae20fba1d0df31cc4d2521b416d7c9eeb7bc991b5581740c0c22a1100e33133b、AGENTS 609ccb96e791596d6c0dfa4187797ec0e1b5f85de05a9df50f67ea02229e6568。
2. roadmap 本任务 P0-0 是“已完成”，进行中表移除本任务，其他任务、优先级、斜体、负责人保留；框图本模块绿色，文字注明实际人工验收通过。一般规则中可解释任务分支待确认状态，但主线本任务不再处于待确认。
3. task.md 记录真实人工批准及推送授权，不把历史模拟当作真实批准。引用和三份永久文档内容准确、简洁，docs/ai 不入站点。
4. 重跑 git diff --check 和 git diff --cached --check；检查新增本目录输出相对空文件的空白格式；使用既有 Node/依赖，在 tools/docs-site 运行 node node_modules/vitepress/bin/vitepress.js build。原 pnpm 入口有已知供应链预检限制，不重试安装、不改锁或策略。无产品实现变化，不需要产品测试或重复控制演练。
5. 确认 develop HEAD 仍基线、outputs/ 只观察状态不读内容、不进入暂存。报告实际检查和未执行项，不虚称已提交／推送。

当前 roadmap SHA-256: 2c24b19c85b9cb1dd125eeb8449cd4df08fbbdfa7bf5b8ea2f3893bac9e0cef8。本轮实现冻结，主控等报告再提交。
