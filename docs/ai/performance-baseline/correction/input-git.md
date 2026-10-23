# 已验收任务的本地提交（等待主控生命周期启动）

只在 /Users/bytedance/.codex/worktrees/performance-baseline/smash-suite 操作。不要读verifier/或其他角色通信；本input是主控已确认的交付事实。第二轮独立功能/代码/文档验收通过，状态收尾核查也通过后主控才发启动信号。代码和人类文档全部冻结，不能改实现/报告/README/路线图/索引，不推送、不合入、不改原工作目录，不重跑模型/采样/鉴权。

开始先确认分支codex/performance-baseline和HEAD基线979caeb1cefedd78b2cebac52ca38f28a84d7563。当前任务工作树全部变更均是本任务独立开发，无他人改动；但仍须git status检查，若发现本input范围外的变化停止回报，不能顺手提交。独立冻结controller/acceptance-freeze-closure.json的所有402文件内容和两删除项必须与实际一致；可只读重算。运行git diff --check。

允许暂存/本地提交的路径：
- apps/video-clipper/README.md
- apps/video-clipper/backend/app/{benchmark.py,sessions.py,worker.py}
- apps/video-clipper/backend/tests/test_benchmark.py
- apps/video-clipper/reports/本任务performance-baseline*及performance-profile-{A,C,D}.json（不要暂存无关旧报告变化）
- datasets/test-videos.md
- docs/plan/roadmap.md
- docs/ai/performance-baseline/ 下全部非忽略的任务材料（包括本轮小验收/冻结记录，不包括runtime、pycache）
- modules/models/tracknet/predictor.py
- modules/rally/{README.md,statistics.py,recognize.py,tracknet_rally.py,scenarios/high.py}
- modules/rally/experiments/{README.md,cases.json删除,replay.py删除,reports/algorithm-decisions-20261019.md}
- pyproject.toml

将上述任务文件明确暂存，检查git diff --cached --check和--stat，确认没有任何.runtime/.venv/模型/原始视频/trace/pycache进入索引。只本地提交，建议消息 feat(video-clipper): add reproducible performance baseline and diagnostics。提交前可以写自己的correction/output-git.md记录已通过独立验收、待人工确认、预计动作；不要在提交后再修改已提交文件制造脏尾巴。提交后通过工具最终消息返回SHA、git status、暂存检查和冻结核对结果，不再改任务文件。若本机Git权限阻止，使用已授权的普通本机权限提交路径，不能修改安全策略。保留worktree，禁止push/merge/reset/rebase等。
