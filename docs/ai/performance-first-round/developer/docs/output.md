# 资料整理轮次 1

## 汇总脚本

已新增 `docs/ai/performance-first-round/controller/summarize.py`。脚本扫描 `apps/video-clipper/.runtime/performance-first-round/<RUN>/<CASE>/result.json`（`*/*/result.json`），只纳入 `status=completed` 的记录；该深度包含单项和 combined run，不会匹配 `evidence/` 下的 result 文件，并读取同一 CASE 下的 `evidence/statistics.json`、`evidence/benchmark-clock.json` 和 `resources.jsonl`。正在运行、状态不完整或文件无法解析的记录会排除并写入摘要 JSON 的 `excluded` 字段。

从仓库根目录用已有、已安装 matplotlib 的 Python 环境运行：

```sh
.venv/bin/python docs/ai/performance-first-round/controller/summarize.py
```

脚本从 controller 脚本路径的 `parents[4]` 得到本仓库根目录；该路径层级为 `docs/ai/performance-first-round/controller/summarize.py`。脚本会生成 `apps/video-clipper/reports/performance-first-round/measurement-summary/summary.json`、`summary.csv` 和每个已完成 run/case 一张静态 PNG 资源曲线。它不会安装依赖、读取或复制视频和长日志，也不会改写原始测量证据。缺失数据保留为空；曲线无有效值时显示“无有效数据”，不填零。曲线横轴由 `benchmark-clock.json` 的真实 `benchmark_start` 定义，单位为秒；CPU 为单核百分比，RSS 为 GiB，MPS allocated/driver 分列 MiB，工作区曲线为扣除源文件后的 MiB。汇总 JSON/CSV 还保留包含源文件的工作区逻辑峰值。MPS 不与 RSS 相加。

## 当前扫描结果

本轮读取时发现三个已完成记录：

| run / case | 状态 | 完整耗时（秒） | 准备（秒） | 识别（秒） | 成片（秒） |
| --- | --- | ---: | ---: | ---: | ---: |
| opt01-d / D-short | completed | 318.382 | 0.549 | 304.737 | 13.096 |
| opt02-d / D-short | completed | 290.951 | 0.548 | 277.601 | 12.802 |
| opt03-c / C-short | completed | 114.028 | 0.435 | 94.108 | 19.486 |

虽然任务输入时标为运行中，扫描时 `opt03-c/C-short/result.json` 的状态已经是 `completed`，因此它会纳入脚本摘要。扫描时尚无 A-case 完整运行记录；主控计划继续处理 A 单项。主控反馈 C 组合仍在测量；只要其记录完成，新的 `*/*/result.json` 扫描会自动纳入。摘要脚本和 PNG 本轮按主控要求尚未运行，故对应生成物尚不存在；主控可在测量空档运行脚本刷新实际结果。

脚本会完整导出每条统计中的子项秒数和工作计数，并从资源逐行记录汇总 CPU、RSS、MPS、工作区与剩余磁盘观测峰值/最小值、样本数、最大采样间隔和采样错误。当前每个已完成记录均包含 `statistics.json`、`benchmark-clock.json` 和 `resources.jsonl`，现有资源记录分别为 315、288、114 行；采样错误为 0，最大间隔分别约 1.025、1.028、1.022 秒。单次耗时不自动判定通过、失败或稳定百分比收益；源差异与结果等价仍由主控核对。

## 缺口

- A 单项完整测量尚未出现在本轮读取快照；后续单项或组合 run 完成后，脚本重跑会自动纳入。
- 当前脚本不对结果等价、效果或优化是否通过作判断。
- 摘要及资源曲线尚未生成，因为主控正继续运行测量；请在测量空档执行脚本。


# 第2轮：独立验收后文档状态收口

## 状态与证据同步

首轮独立验收已通过；任务分支按“已完成，待人工确认”记录，等待人工确认集成，尚未合入或推送。首轮保留 OPT-01 诊断计时、OPT-03 缓存及 OPT-04 两处 copy 简化。OPT-02 实验虽完成，但因误删本轮暂缓采用，不实施条件合批；8.62%仍只是单次差额，不能当作确定的独立收益。原版 318.38 秒与 339.24 秒的运行时差异仍未定位。路线图任务 5 仍为“进行中”，原基线及 Windows 任务保持不变。

独立验收摘要及结论链接已加入正式报告：56 个冻结文件 SHA 匹配；功能、代码和文档验收通过；真实 MPS 下 C 四窗口与无帧 ID 探针一致，最终 D 区间、导出和保存姿态信号与原版相同。验收详情链接由正式报告指向执行目录记录。

## 本轮改动与验证

状态与链接更新涉及：

- `apps/video-clipper/reports/performance-first-round.md`
- `apps/video-clipper/README.md`
- `docs/features/performance-optimization/README.md`
- `docs/features/performance-optimization/first-round.md`
- `docs/plan/roadmap.md`
- `modules/models/README.md`
- `modules/models/tracknet/README.md`
- `modules/models/keypoint_rcnn/README.md`
- `docs/ai/performance-first-round/.gitattributes`

`.gitattributes` 仅在本 AI 执行目录对 `*.patch` 将 unified-diff 上下文行按数据处理，保留其字节；未修改 patch 文件或全局设置。

验证：`git diff --check`；指定 patch 的 `git diff --no-index --check /dev/null .../opt01-statistics.patch`；受影响文档的本地相对链接存在性检查。产品源码未修改，本轮前后 SHA 将在下方记录。未运行产品测试、模型或测量脚本；未暂存或提交。

本轮文档收口前后产品源码 SHA 一致：

- `modules/rally/recognize.py`: `ee2c0a949522ab6c809bf7da9afb4a4956dda9ad3b6da4fc389e8f0598e8bcd0`
- `modules/models/keypoint_rcnn/__init__.py`: `379ed20f3c6e228efecd08828ee8b6b6dc6a89084dd19173163ef1cab9c19316`
- `modules/models/tracknet/predictor.py`: `df737b3bac7ae2ecba2a8ce6337cb56d7350cc053de54f4b950d997a634679aa`


补充收口：正式报告中的“C 缓存可保留进入验收”已改为“C 缓存验收通过并保留”；姿态计时段的“尚待独立复验”已改为“独立复验通过”。未改动数字或效果结论。复查报告后未发现其他待独立复验状态措辞。


# 第3轮：专题表格两格状态修复

仅将 `docs/features/performance-optimization/README.md` 中 OPT-01 和 OPT-03 行的状态格由“进行中”改为“已完成”；两行进展说明、OPT-02“待办”及其余内容均未改。`git diff --check` 通过；未跑测试或模型，未提交。
