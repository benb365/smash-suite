# OPT08C 主目录集成验证与本地提交

唯一主目录 /Users/bytedance/workspace/experiments/smash-suite，develop HEAD c62527982a6bcd6fc95cb00572f346d52d36fffb；源已验收任务 c36b0dc673d9cde65f160fbf6e8e2cd629174b68，源worktree保留且clean。主控已采用本轮独立真实功能/代码/文档符合结论，用户授权不再逐项确认、自动本地集成、不push。原输入与源码冻结为历史，不能拿primary更新后taskSHA误报源冻结改变。

只读本input/integration-freeze/evidence-preservation/正式报告和必要源码，不读developer通信正文（可核对字节SHA）。核对freeze的21个原staged内容SHA/路径，允许本任务两个目录与feature README/roadmap，无产品修改。规划index只本任务结论和后续09A认领，working仍有用户改稿，不git add planning整份、ideas、untracked草稿/outputs。核对18 accepted源文件复制，task只主控集成阶段元数据例外记录source/destSHA；12runtime与2sidecar（viewer已有主控原图）大小/SHA全部一致。

执行5项test_experiment.py与cached/working diff check；本轮只实验报告不跑backend/frontend/模型。核查正式报告灰度浮点差/default allclose False、840ms缺口/240ms新增、旧色控制非本轮重跑与无truth限制，保守不采用不误作准确率失败。通过后只写自己的verifier/integration-output.md，分别说明功能/代码/文档/集成检查和限制；暂存integration-freeze、本input及自己的output，保持21原staged内容不变。cached check与HEAD再核对后一次本地commit `perf: integrate TrackNet grayscale trial results`，不push、不归档；完整SHA/status后暂停。失败只写output停，不修实现。
