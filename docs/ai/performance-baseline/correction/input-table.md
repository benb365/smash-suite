# 第三轮：修复报告首表 Markdown 分隔行

用户明确要求“报告开头的表格显示不正常，修复一下”。在 /Users/bytedance/.codex/worktrees/performance-baseline/smash-suite 原分支继续，不创建新工作目录。先git status，当前HEAD 4a58b89862aae6496cfb639f5b29c2217e655a6f，工作树干净。不要读其他角色通信，仅读本input及实际报告。

已核实apps/video-clipper/reports/performance-baseline.md“六份正式结果”的首表表头8格，分隔行9格，数据行8格。最小修正：仅删除该分隔行末尾多余的一个---:格，保留8格（首格左对齐，其余7格右对齐）。不改数值、文字、图表、算法或其他文档，不重新测量/采样/鉴权。不要引入新工具或测试文件。

修后检查该报告所有Markdown表的表头/分隔/数据行列数，且实际git diff只有该行。git diff --check。只写报告这一行及自己的correction/output-table.md，输出标轮次3、HEAD、SHA与验证。不能提交/推送/集成。完成停止写入，主控交独立文档复验后再本地提交。
