# 合入与推送预检

用户已明确同意将本地任务提交 3b0ef65b42b40912ab36ef0cf5b7d573ef7e7707 合入 develop 并推送。你负责机械 Git 操作，由主控决定整合结果。业务只经本目录文档，不继承主控对话，不读 verifier 或联系其他角色。通知只给 output.md 的绝对路径。

原仓库 /Users/bytedance/workspace/experiments/smash-suite，develop 当前预期 2ccf5f60b7638774aded138a8af00801501a72f2。源 worktree /Users/bytedance/.codex/worktrees/single-task-workflow/smash-suite，源分支 codex/single-task-workflow，源提交如上。原目录的 outputs/ 不得读取／暂存／删除。原目录唯一跟踪文件修改是主控此前的 roadmap 自动协作认领行，暂时不要处理。

本阶段仅核对两个目录状态、分支、remote、源提交、暂存区和差异，fetch origin develop 后报告本地与 origin/develop 的提交关系（领先／落后及差异范围）。不打印凭据。不要切分支、合入、提交、推送或改文件；只写自己的 output.md。后续主控根据预检结果另行派发。需要对仓库 Git 元数据写入（fetch）时可在已授权范围申请 escalation。

## 第二阶段：准备单次集成（不提交、不推送）

主控已读预检，亲自核对 develop 与 origin/develop 均为 2ccf5f60b7638774aded138a8af00801501a72f2，领先／落后为 0。原报告把源提交改动写成 roadmap 一增一删，主控实际 git show 确认该源提交是 76 文件、2330 插入、4 删除；请先核实并更正自己的报告，不将原目录未提交差异误当源提交差异。

用户已授权合入与 push；本阶段只准备合入工作树，仍不提交／推送，主控将同步最终状态并独立复核后再派发。原目录必须仍为 develop 和预期 HEAD、暂存区空。确认 roadmap 未提交差异严格只有主控已知的自动协作认领行：原行为 benb365 + develop 已登记开发中，现行为 benb365 + codex/single-task-workflow 独立验收已通过／待人工确认。若出现额外用户修改则保留并报告，不继续。

把这份仅含已知认领行的差异保存到 /private/tmp/smash-workflow-integration-claim.patch，核对可恢复后只反向应用这份差异，使该文件恢复基线；这是消化主控自己此前的认领修改，不得使用全仓 reset/clean/stash，不得触碰 outputs/。随后在原 develop 使用 git merge --squash --no-commit 3b0ef65b42b40912ab36ef0cf5b7d573ef7e7707，只整合已提交源内容，主线暂不生成任何提交。源 worktree integration/ 是本轮通信目录，不在旧源提交中，不要误合。

合入无冲突后，检查源已验收文件匹配，暂存文件均属于源提交，原 HEAD 未变，outputs/ 保留。任何冲突或意外状态先报告；不要擅自改方案。更新本目录 output.md，保留预检历史及更正说明，仅路径通知。
