# 实际优化代码集成准备

轮次integration-1。用户2026-10-21确认OPT03/04实际优化代码合入develop；全部本轮测试/报告/原始证据保留。OPT01只保留诊断结论和历史证据，新增细分统计不作为本轮优化代码合入；OPT02批处理暂缓，依赖先改善找球后的D算法处理，需要更新优化方案。不推送。

工作目录仅 /Users/bytedance/.codex/worktrees/performance-first-round/smash-suite，分支codex/performance-first-round，基点55c6f0c13c4eff35dc960da6328359711117afda。只读本输入、相应人类文档/源码/必要证据，不读verifier/或其他developer通信。主控记录task.md你不读写。只改下面授权范围，输出写本目录integration-output.md；完成后停止，不提交、不合入、不碰主目录。

## 产品代码选择

1. TrackNetPredictor与C observe中的OPT03缓存及OPT04复制删除完全保留，不改其数值/分组/生命周期。
2. PoseEstimator恢复至develop基线的简洁单图实现，只删除原有cv2.cvtColor(...).copy()中的.copy()。可读取`git show 5c946e9:modules/models/keypoint_rcnn/__init__.py`取得原文件，再仅去掉该处copy。不要保留OPT01新增_prepare/_convert封装、statistics参数、monotonic或三个细分时间项。
3. recognize.py仅将姿态调用`raw = model(crop, statistics=stats)`恢复为`raw = model(crop)`；原有pose_inference_s/calls/person_crops的基线统计保持，C缓存逻辑原样保留。
4. 删除仅验证OPT01细分接口的modules/rally/tests/test_pose_statistics.py（完整历史仍在Git，原106项测试记录不删不改）。OPT03有意义测试保留。不改任何其他产品代码/测试；不新增开关或无用兼容。

## 方案和状态文档

允许修改：docs/features/performance-optimization/{README.md,first-round.md,reports/first-round.md}、modules/models/keypoint_rcnn/README.md、modules/models/README.md、modules/models/tracknet/README.md、apps/video-clipper/README.md。不要改主目录或roadmap（主控在实际集成时处理）。

- 当前状态写“用户已确认OPT03/04代码集成，准备合入；OPT01诊断结果保留、细分计时代码不纳入产品；OPT02暂缓”。不提前宣称已合入/已推送。
- 全部测量/数值/效果/版本来源保持；报告明确“保存的测量版本包含OPT01诊断，交付代码仅03/04；未为删诊断后的交付版新增性能测量，不把旧秒数当新基线”。原106项通过是历史测量/验收版本，本轮最终代码测试由独立验收另记，不篡改原记录。
- OPT01结论写清诊断有价值：159.81秒姿态入口中159.31秒为模型调用约99.7%，外壳准备和返回约0.48秒，因此外壳不是优先热点；模型调用含内部缩放/归一化/网络等，不能当作纯网络或Python成本。本身不提速，不继续拆壳或保留诊断实现。
- OPT04已验证输入和结果等价，用户确认作为简化合入；C递进识别耗时增加1.07%及原因/可重复性未验证原样保留，不改成已证明稳定提速或没有任何性能退化。
- OPT02在专题首轮表标为“阻塞”，原因明确依赖D找球后的算法稳健性优化，不能误写成依赖OPT05粗筛或先改模型。新增简短“OPT02前置依赖与恢复条件”：先改善D姿态/动作证据到回合结束判断对扰动的处理，不能因姿态小变化漏掉230.193秒确认仍在回合中的点；这是路线图任务3“回合效果与场景适应”中的D子项，不要求整个任务3所有场景全完成。
- 前置算法改进须先独立通过已有效果验收，再以改进后的“逐人姿态”作为批处理对照，单独复验批处理（已知点+完整区间/导出）；通过后再组合。不提前认定算法优化必能解决误删，不实施条件批处理，不改效果门槛。OPT02方向和全部失败证据保留。
- keypoint README撤掉statistics参数示例和不再存在的三个细分接口，稳定产品接口只model(image)；测量诊断结论可链接报告。详细first-round文档保留历史实验设计，但顶部及OPT01节注明01只用于测量、实际集成03/04，避免当作当前API承诺。

## 验证与交付

只跑必要静态检查：确认pose代码与develop相比仅少一次copy，recognize与当前HEAD相比仅撤销statistics实参，TrackNet文件及OPT03测试SHA不变，产品无batch；本轮没有新增算法/参数改动。git diff --check；受影响相对链接和标题锚点有效。不要跑完整性能实验/模型/后端测试，独立验收将重跑后端并做必要数值对照。

输出实际修改清单、静态检查、版本边界与待验收事项到integration-output.md，然后停止写入。全部JSON/CSV/PNG、历史冻结/补丁/日志、基线工作目录/权重不动，不删原始数据。
