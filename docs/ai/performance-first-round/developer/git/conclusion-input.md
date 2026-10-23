# 结论报告重整：本地提交输入

只有主控明确启动后才执行。工作目录 /Users/bytedance/.codex/worktrees/performance-first-round/smash-suite；分支codex/performance-first-round，预期HEAD40fc44ca2456e326360b05190ef77a6ec579046e。启动表示主控已核对独立本轮复验通过。不得读取其他角色通信文件，不改正文、源代码、证据，不合入/推送、不动主目录，不删除.venv或工作目录。

先检查当前状态和controller/conclusion-freeze-2.json的轮次conclusion-2、28项摘要匹配；若不符停止，不自己修复。允许写本目录conclusion-output.md，记录冻结/范围/差异检查，注明准确提交SHA以Git HEAD和最终工具结果为准。输出只写一次并参与本次提交，提交后不改写造成dirty。

严格只暂存以下文件：
- apps/video-clipper/reports/performance-first-round/README.md
- docs/features/performance-optimization/reports/first-round.md
- docs/features/performance-optimization/first-round.md
- docs/features/performance-optimization/README.md
- docs/ai/performance-first-round/task.md
- docs/ai/performance-first-round/developer/docs/conclusion-input.md
- docs/ai/performance-first-round/developer/docs/conclusion-output.md
- docs/ai/performance-first-round/verifier/conclusion-input.md
- docs/ai/performance-first-round/verifier/conclusion-output.md
- docs/ai/performance-first-round/controller/conclusion-freeze.json
- docs/ai/performance-first-round/controller/conclusion-freeze-2.json
- docs/ai/performance-first-round/developer/git/conclusion-input.md
- docs/ai/performance-first-round/developer/git/conclusion-output.md

核对暂存范围只有本轮文档及执行记录，git diff --cached --check通过后本地提交：docs: organize performance conclusions by stage and test type。不运行产品测试或测量。返回新的SHA、分支、文件数量及最终status；完成后停止。
