# OPT08A 主目录集成验证与提交

主控已采用独立功能/代码/文档验收，并按用户“无需再确认”授权准备自动集成、不push。唯一主目录 /Users/bytedance/workspace/experiments/smash-suite，develop HEAD0467b6590d16e4dc60ecc3ae6aa0a40063da8b51；源worktree仍保留，已验收任务a960998b367aea63ca2f10e01059be9e3c542614。禁止读任意developer目录，不修改实现/正式报告/规划working草稿。

核对integration-freeze的18个staged SHA及19原暂存路径，允许两个OPT08A目录和feature README/roadmap；无产品/其它路径。规划index只本任务结论和后续08C认领，working另有用户改稿；不得git add整份planning文件或ideas。核对preservation记录14个accepted源文件（task仅主控当前状态元数据例外，manifest记源/目标SHA），22个runtime原始/独立证据、TrackNet review sidecar及现有viewer截图大小/SHA；源码冻结11/运行15为任务历史验收不改。

执行test_run.py的3项定向检查、cached/working diff check；本轮无产品行为变更，不跑backend全量/frontend或模型/视频。主控当前无模型任务。读正式报告和summary确认本轮新控制/旧07A输出等同关系、单次成本/输出缺口与不采用的保守边界、无truth假标签。核对主目录源HEAD未变且来源clean。

通过时只写自己的verifier/integration-output.md，列实际核对数/测试/边界/用户dirty保留。暂存本input及自己的output，保持原19个staging条目不变；cached check及HEAD复核后一次本地commit `perf: integrate TrackNet input size trial results`，不push不归档不更改其它index。报告完整SHA与status后暂停。失败只写output并停，不自行修实现。后续root检查再归档。
