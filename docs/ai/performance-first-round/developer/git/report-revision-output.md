# 报告整理提交核对

- 基线：分支 `codex/performance-first-round`，HEAD `ba0fd88b4563c5366a5dcdac8c5a941573a1a65b`；暂存前索引为空。
- 冻结核对：`report-revision-freeze-2.json` 的 34 个文件均存在且 SHA 匹配；冻结列出的旧报告正文已删除。
- 范围核对：工作区改动均属于明确暂存清单；仅文档新增、修改和旧正文删除。`.venv` 是未跟踪符号链接，排除提交。
- 提交前检查：暂存后执行 `git diff --cached --check`，并确认暂存清单与差异统计。
- 准确提交号以 Git HEAD 和提交工具结果为准。
