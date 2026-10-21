# 所选优化代码提交核对

- 基线：分支 `codex/performance-first-round`，HEAD `55c6f0c13c4eff35dc960da6328359711117afda`；暂存前索引为空。
- 范围：仅本轮选定的代码与文档、删除的 pose statistics 测试，以及 integration/evidence-preservation 执行记录；`.venv` 符号链接排除。
- 暂存检查：按输入列明的路径暂存，核对 staged 路径和差异统计；运行 `git diff --cached --check`。
- 提交号以 Git HEAD 和工具结果为准。
