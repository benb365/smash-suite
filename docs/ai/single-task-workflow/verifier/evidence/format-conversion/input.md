# 已授权证据格式转换（机械任务）

只处理本输入列出的 8 个历史 .diff，不读真实 developer/，不改实现、标准、验收结论、whitespace 策略，不提交/合入/推送。

任务根目录：/Users/bytedance/.codex/worktrees/single-task-workflow/smash-suite。
只写该根目录 docs/ai/single-task-workflow/verifier/evidence 内下列 .diff 与本目录 output.md；必要的临时脚本只放 /private/tmp，不新增永久代码或配置。需写权限时按已批准范围申请 escalation。

目标：把含单个空格上下文行的合法 unified diff 转换为合法零上下文差异。只能省略未改上下文，并据此拆分/调整 hunk 坐标与计数；文件路径、每条真实增删内容及其原/新行位置必须保留。不能简单裁空格破坏补丁结构，不改原始新增/删除内容；保留其他补丁头信息。

原文件外部快照（只读，禁止修改）：/private/tmp/smash-evidence-format-i3juvnt5

限定文件（相对于 evidence）：
- closure/original-roadmap.diff
- closure/roadmap.diff
- rehearsal/accepted-implementation.diff
- round2/startup.diff
- round2/tracked.diff
- round3/change-from-round2.diff
- round3/startup/implementation.diff
- tracked.diff

转换后运行适当的补丁语法/增删内容坐标一致性检查，并对每个新增 .diff 执行相对空文件的 git diff --no-index --check，以覆盖未跟踪文件。不能绕过检查或修改策略。所有结果只写本目录 output.md，明确实际执行、失败和未执行；结束通知只给 output.md 绝对路径。外层还会独立比对快照和转换后内容。
