# 所选优化代码本地提交

轮次 integration-commit-1。工作区 `/Users/bytedance/.codex/worktrees/performance-first-round/smash-suite`，分支 `codex/performance-first-round`，起始HEAD `55c6f0c13c4eff35dc960da6328359711117afda`。主控确认 integration-1 独立验收通过后才派发执行。本输入仅负责机械Git，不读取 verifier/ 或 implementation developer/ 通信，不改变代码/证据/验收标准。

用户确认实际OPT-03/04合入develop，本阶段先本地提交所选代码及完整报告记录；不合入、不推送、不删除worktree。本轮全部历史证据保留；细分OPT-01实现不集成，OPT-02批处理不集成。

## 操作

1. 检查分支和状态；确认无未预期改动。所有改动应在以下允许范围：apps/video-clipper/README.md、docs/features/performance-optimization/、modules/models/README.md、modules/models/keypoint_rcnn/{README.md,__init__.py}、modules/models/tracknet/README.md、modules/rally/recognize.py、删除 modules/rally/tests/test_pose_statistics.py、docs/ai/performance-first-round/ 下本轮新增 integration-/evidence-preservation 文件及 task.md。本轮的 verifier 结果属于允许保存的独立执行记录，可以按路径暂存但不要打开正文。
2. `.venv` 符号链接和任何 `.runtime` 原始大数据必须排除。主目录文件不在本阶段操作范围。
3. 只暂存上述改动，核对 staged 路径。运行 `git diff --cached --check`；新文件不得新增空白错误，历史原始CSV/日志本轮未变更。
4. 写本角色输出 developer/git/integration-output.md，记录本轮动作和检查（提交哈希不需自指向嵌入文件）。将输出纳入同一提交，然后再次差异检查，以 `perf: select approved preprocessing optimizations for integration` 本地提交。
5. 输出最终准确提交SHA、分支、提交stat和状态，停止。不执行merge、push、worktree归档或其他修改。Git元数据需要权限时，仅申请该明确已授权动作。
