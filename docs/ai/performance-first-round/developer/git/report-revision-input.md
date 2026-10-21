# 报告整理本地提交

仅在主控明确启动后执行；此前没有提交授权信号。工作目录 /Users/bytedance/.codex/worktrees/performance-first-round/smash-suite，分支 codex/performance-first-round，预期HEAD ba0fd88b4563c5366a5dcdac8c5a941573a1a65b。不得修改主目录或任何产品文件；不合入/推送，保留 .venv 和工作目录。

主控启动表示本轮独立文档复验已通过。你不读取其他开发或verifier通信目录；检查controller/report-revision-freeze-2.json的冻结文件和删除文件匹配。只运行必要Git操作，不重新测试或整理文件。

明确允许暂存的文件（不存在的旧正文作为删除暂存）：
- AGENTS.md
- apps/video-clipper/README.md
- apps/video-clipper/reports/performance-first-round.md
- docs/README.md
- docs/features/performance-optimization/README.md
- docs/features/performance-optimization/first-round.md
- docs/features/performance-optimization/reports/first-round.md
- docs/plan/roadmap.md
- modules/models/README.md
- modules/models/keypoint_rcnn/README.md
- modules/models/tracknet/README.md
- docs/ai/performance-first-round/task.md
- docs/ai/performance-first-round/developer/docs/revision-input.md
- docs/ai/performance-first-round/developer/docs/revision-output.md
- docs/ai/performance-first-round/verifier/report-revision-input.md
- docs/ai/performance-first-round/verifier/report-revision-output.md
- docs/ai/performance-first-round/controller/report-revision-freeze.json
- docs/ai/performance-first-round/controller/report-revision-freeze-2.json
- docs/ai/performance-first-round/developer/git/report-revision-input.md
- docs/ai/performance-first-round/developer/git/report-revision-output.md

写自己的report-revision-output.md：只记录准备提交时已检查的范围/冻结/空白，注明准确提交结果以工具返回和Git HEAD为准，不写自指提交号。该输出一次写完再暂存提交，不在提交后改写它造成新dirty。不读verifier输出，但允许按上面明确路径暂存。先检查工作区/暂存区无意外文件，严格暂存allowlist，git diff --cached --check，确认只有文档修改和旧正文删除/新正文新增；git commit -m 'docs: clarify performance comparisons and organize round report'。若冻结或范围不符停止并报告，不修复文档。完成报告提交SHA、分支、文件数量与最终status；不运行任何push/merge操作。
