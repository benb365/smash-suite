# OPT-08C 主目录集成验证结果

轮次：第1轮集成。主目录冻结基线 `c62527982a6bcd6fc95cb00572f346d52d36fffb`；源任务提交 `c36b0dc673d9cde65f160fbf6e8e2cd629174b68`。

## 结论

指定范围的集成核验通过，可以本地集成提交。实验结论保持保守不采用 gray3；区间差异仅表示候选输出有变化，不作为准确率失败结论。

## 功能与证据

- 按任务要求独立重跑 `docs/ai/opt08c-gray/test_experiment.py`：5项通过。系统 Python 3.9.6 未安装 pytest；使用源任务 worktree 的 Python 3.11.16 环境运行，结果为 `5 passed`。未重跑模型、backend/frontend 或产品测试。
- 正式报告与验收报告记录：gray9/gray3模型输入的灰度复制值一致，但首层/heatmap不是位级或默认 `torch.allclose` 等价；候选完整识别区间相较原色控制有840ms缺失、240ms新增。灰度候选与旧彩色控制均为4200帧、1400次TrackNet调用。上述区间变化无匹配人工标注，不能解释为已证实漏检或误检。
- OPT-08A原色控制为历史单次运行，未在本轮重跑；耗时为单次观察，不据此声称稳定加速。报告中的本地viewer证据只定位一个边界差异，不代替人工标签或全片准确率验收。

## 代码、文档与集成范围

- 主目录HEAD仍为冻结基线；源任务worktree HEAD等于已验收提交，worktree干净。产品源码无变化。
- `integration-freeze.json`列出的21个原暂存路径及index字节SHA全部匹配。包含本任务结果的feature README与roadmap暂存版本也与冻结SHA一致；工作区另有修改保留在未暂存状态。
- evidence-preservation中18个接收文件副本、12个runtime文件及2个sidecar均与记录的大小/SHA匹配。task.md为主控集成阶段元数据例外；源SHA保留于证据记录。
- 文档结论明确候选不采用并转向OPT-09A；没有把runtime、ideas、其它未跟踪草稿或outputs纳入冻结范围。暂存与工作区 `git diff --check` 均通过。

## 限制

没有匹配本视频的人工真值；独立viewer未再次复看，主控已实际播放且保留局部截图和review记录。未运行彩色完整重跑或产品全量测试；这些限制不改变本轮已授权的实验报告集成结论。
