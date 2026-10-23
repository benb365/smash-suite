# OPT06 主目录集成验证与本地提交

用户明确授权验收后自动集成。主控已采用任务独立验收并准备index，只集成当前候选“不采用”的诊断证据。不要读任何developer通信目录，不改生产实现/标准/规划working草稿。

唯一主目录 /Users/bytedance/workspace/experiments/smash-suite，develop HEAD4910e1e5af66d4baebc8373bc6d138645510a996。阅读integration-freeze.json、evidence-preservation.json、controller/integration.md、task及人类报告。已验收来源2e25c947e7af597343ee7348cc0baea071008574，源worktree仍保留且clean。

核对freeze所列31个index内容SHA全部一致；32个原staged路径加本input属于允许范围：docs/ai/opt06-scan、apps/video-clipper/reports/opt06-scan、docs/features/performance-optimization/README.md、docs/plan/roadmap.md，不得有其它路径或产品代码。两规划文件index是已提交基线加主控进度，working文件另有用户改稿，不得git add整份草稿。检查cached diff planning仅本任务状态与后续08A认领，没有把用户ideas、其他任务规划、SVG或optimization-details纳入。核对7个保存runtime JSON大小/SHA，及27源提交文件（task.md仅当前状态改为验收通过/准备集成，允许这一主控元数据变动；其余字节一致）。

主控MPS已停止，现在可运行6项定向测试；git diff --cached --check、git diff --check。未改产品代码不需后端全量/前端检查或再跑模型/视频。核对报告准确限制本轮候选，不宣称真实跳过/准确率。

若均通过，只写自己的verifier/integration-output.md：通过项与实际测试数、源/主版本、运行数据核对数、保留用户dirty事实、无产品代码改变。暂存本input和自己的output（其余staging保持原样），cached check且复核HEAD未变后，本地一次commit `perf: integrate coarse scan diagnostics`。不push、不归档、不改其它文件或index条目。报告最终commit SHA和status后暂停。若任何检查失败，写自己的output并停，不提交，不自行修实现。
