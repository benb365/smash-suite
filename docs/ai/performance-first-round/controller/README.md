# 本机首轮测量恢复入口

## 集成后恢复入口

首轮 OPT-03/04 已按用户确认进入 develop 集成，全部原始运行文件已复制到主工作区 `/Users/bytedance/workspace/experiments/smash-suite` 的同名 `.runtime/performance-first-round/` 目录；查看器 JSON 同样位于主工作区。逐文件校验见 `evidence-preservation.json`。本轮任务及测量 worktree 将在集成验证后归档，原性能基线 worktree 按用户要求继续保留。下文固定路径和历史控制脚本保留执行时原貌，复跑前须重新准备测量 checkout 并核实路径，不应直接在 develop 覆盖原始证据。

## 历史固定目录

任务源码、正式报告和新证据在`performance-first-round/smash-suite`；测量专用checkout为相邻`performance-first-round-measure/smash-suite`，基底均为`5c946e9e6186d052624ca6f853a62d40f034f6e8`。原基线worktree和准备权重单独保留。

`measure.py`固定了这些本机路径，复用产品`app.benchmark`，不新增公开接口。运行前检查三份测量源码是否仍符合`measurement-source-state.json`，从基底重建所选版本；测量后再次核对源码SHA。每次必须用新run_id，已存在的证据不覆盖。只允许三个产品源文件的已批准增量补丁。

## 已执行的版本选择

在任务根目录，入口为`.venv/bin/python docs/ai/performance-first-round/controller/measure.py RUN_ID CASE [版本选择]`；该命令由控制脚本检查输入/权重并运行真实识别和编码。CASE为`A-short`、`C-short`或`D-short`。

| run_id | CASE | 版本选择 |
| --- | --- | --- |
| opt01-d | D-short | `--patch controller/variants/opt01-statistics.patch` |
| opt02-d | D-short | 依次应用01与02补丁；失败变体，只留追溯，不再纳入本轮产品 |
| opt03-c | C-short | `--patch controller/variants/opt03-cache.patch` |
| opt04-a | A-short | `--tracknet-copy-only` |
| combined-c | C-short | 依次应用03与04-tracknet补丁 |
| combined-d | D-short | `--final`，直接冻结三份任务目录最终源码；已无batch |
| opt01-d-control | D-short | 与opt01-d相同，因D模型阶段异常降时追加一次原版对照 |

上表补丁路径的`controller/`实际位于`docs/ai/performance-first-round/controller/`；工具收到的是该完整路径。具体补丁SHA、源码SHA、UID及完成状态逐次存于`freezes/`。控制脚本保留原runner的`kind=baseline`字段，表示不附加剖析器的正式运行；本轮版本由run_id及冻结文件辨认，不代表旧基线被覆盖。

## 核对与曲线

`validate.py 候选CASE目录 参考CASE目录 输出JSON`比较已保存区间、导出参数、音视频全部解码与结构，D另比较保存的姿态信号。差异不会被自动解释为效果通过；用户确认的回合中误删记录在正式报告配套`d-batch-changes.json`。

`summarize.py`扫描已完成运行生成正式报告的资源JSON/CSV及PNG；按真实单调时钟对齐，分列CPU、RSS、MPS与工作区，保留采样错误和最大间隔。测量间隙再运行，避免影响计时。正常环境通过任务临时`.venv`链接复用，禁止提交该链接；原Python环境与依赖版本由基线和各轮manifest记录。

`probe_tracknet.py`是主控批准给独立验收的真实帧探针，参考预处理须核对基底源码；`run_probe.py`固定torch4/OpenCV1。原始探针结果与完整成片在应用`.runtime/performance-first-round/`，不提交Git，保留本机。后端测试实际入口及pnpm供应链校验限制见正式报告。
