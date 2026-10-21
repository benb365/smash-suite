# OPT-03/04 集成准备独立验收

## 轮次与隔离

轮次 integration-1。工作区 `/Users/bytedance/.codex/worktrees/performance-first-round/smash-suite`，冻结文件 `docs/ai/performance-first-round/controller/integration-freeze.json`。开发已停止。只读取本输入、实现、所属文档和原始证据，不读取 developer/ 通信目录或其他角色会话；不修改实现或验收标准。验收仅写 verifier/integration-output.md、自己的临时脚本、检查日志和 JSON。先核对冻结，结束再次核对。

## 用户授权与代码选择

用户确认 OPT-03/04 实际优化代码合入 develop；本轮所有测试结果、报告和失败证据保留。OPT-01 只留诊断结论/历史证据，不集成新增细分计时代码；OPT-02 本轮暂缓，不加条件批处理，不降低效果门槛，不更换模型/设备/线程/采样/阈值。仍需通过验收才能合入；当前尚未合入或推送。

基点 develop `5c946e9e6186d052624ca6f853a62d40f034f6e8`；已验收测量版本与报告 `55c6f0c13c4eff35dc960da6328359711117afda`。本次选择后的预期：

- PoseEstimator 相对 develop 只有移除 cvtColor 后的 `.copy()`；接口回到 `model(image)`，逐人单图。recognize.py 相对 55c6f0c 只有姿态实参移除 statistics；原 pose_inference_s 与调用/裁剪计数不变。
- TrackNet OPT-03/04 实现和缓存测试相对 55c6f0c 完全不变。C 才启用已知帧身份、最多3帧缓存；保持组序、数值、推理调用数；A/D 不启用缓存。两处仅删确证多余复制，不加其他优化。
- 删除仅检查 OPT-01 细分接口的 test_pose_statistics.py，保留所有原始证据及历史版本。当前后端预计105项；历史106项记录不能改写为当前版本。
- 不新增性能测量；历史测量含 OPT-01 计时，本交付没有新的墙钟基线，不将旧秒数冒充新版本实测。

## 必要独立检查

1. 核对代码及接口；完整差异中无批处理/OPT-01新统计，TrackNet及测试SHA不变。历史测量 JSON/CSV/PNG 和早期冻结/执行证据未被修改（新 task 授权附记除外）。
2. 运行当前后端检查。package.json 的 test:backend 实际为 `.venv/bin/python -m pytest`。已有 pnpm 包管理器入口因自动下载 watchpack 被供应链策略拦截；本次直接运行同一 Python 命令，不安装或下载包。记录结果及既有警告。无需前端检查。
3. 真模型数值对照：使用保存的8个真实人物裁剪，核对当前简化单图实现与55c6f0c测量版本在不启用细分统计时输入张量和输出数组严格相同、裁剪未变化。可以 `git show` 参考源码在临时模块中加载，不改被测文件。固定现有权重 `/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/prepared-models/pose_kpRCNN.pth`；torch线程4、cv2线程1，CPU、正常用户。权重只读，不下载。参考与当前可共享同一个底层 eval 模型以减少重复加载。参考的 `_prepare` 可核对 tensor，当前模型输入可用 forward_pre_hook 捕获，严格 np.array_equal 比较每个返回数组。原始采样 `apps/video-clipper/.runtime/performance-first-round/probes/d-samples.json`，来源及实际视频 `d-samples-source.json`；仅真实探针，不代表人物真值。顺序解码取0/300/3600/7524各两框；与 person_signals 相同扩边 x±0.20h、y±0.12h（检查源码取整和边界）。保存输入sha、权重sha、版本、8项数值核对结果。此检查不是新性能测量，不报性能秒数。不读取旧 developer 探针实现。
4. 轻量文档检查：OPT-01结论模型159.31/入口159.81秒约99.7%，外层约0.48秒，不等同纯网络/纯Python。OPT-03/04准备集成状态和原始证据边界正确；C递进+1.07%原因未知，用户接受等价简化。OPT-02 具体前置是路线图任务3内D找球后证据/结束判断稳健性，不必等待所有场景，也不是OPT-05粗筛；前置算法独立通过效果验收后，以改善后的逐人版重验批处理的230.193秒确认点和完整区间/导出，再组合。后续方向未授权实施。
5. 文档相对链接和锚点、差异检查。既有原始summary.csv CRLF及原始backend-development.log末尾空行不改写，可在严格差异检查中只排除这两个文件并记录；工作区docs/ai链接明确不在文档站发布，不作为缺陷。任何新文档不得依赖此豁免。
6. `.runtime` 证据已从任务WT复制到主目录，按照 controller/evidence-preservation.json 对两个源/目标目录逐文件核对集合、字节和SHA，共168文件1493932296字节。此数据Git忽略，后续归档任务WT前必须保证保存完整。主目录 `/Users/bytedance/workspace/experiments/smash-suite` 的 ideas.md SHA应为 `5f0066e40861792a09d79324602ad890ece794fc585534ce8bc8093f3c23bba5`，outputs/ 不读不改。基线工作目录必须保留，不归档。

## 验收结论

分别给功能/代码/文档结论；只启动、缺有效数据或异常未解释均不算通过。原完整短片功能/原始数值证据已独立验收，本次不重跑长片/完整性能流程；明确沿用原证据的范围与本次新增数值检查的边界。写明轮次、冻结版本、实际检查、结果及阻塞，最后给是否允许所选03/04代码进入集成。
