# 回合识别实验入口

在仓库根目录、共同 Python 3.9+ 环境中使用。

- `python -m modules.rally`：从视频运行当前场景方案，详见[模块说明](../README.md)。
- `python -m modules.rally.experiments.replay --output modules/rally/.runtime/replay.json`：重放保留的 A/C/D 观测，对照确认记录中的原始区间。用 `--scene` 或 `--sample` 选择范围。
- `python -m modules.rally.experiments.run_live_tracknet --video ... --output ...`：文件原速输入诊断；可用 `--mode offline` 尽快读取。
- `python -m modules.rally.experiments.run_tracknet`：早期恒定帧率基线诊断，具体参数见源码或 `--help`。

`cases.json` 固定 16 个回放用例、输入文件路径、校验值和期望区间。输入按清单中的路径读取，主要位于模块 `.runtime/`；A2 仍引用外部历史缓存。评估标注仍位于 `datasets/`，算法报告与配套 JSON 位于本目录 `reports/`。

高视角用例若只使用完整缓存中的一段，需声明 `window`：`source_frame_start` 为起始帧，`source_frame_end_exclusive` 为不包含的结束帧，`clip_time_start_ms` 为片段在缓存中的起始时间。回放先校验完整缓存，再按窗口截取，将帧号、时间和观测可用时间归零；不修改原缓存。没有 `window` 时使用全部输入。A2-01 使用帧 `[0, 2421)`、起始时间 0 毫秒；A2-02 使用帧 `[2472, 4500)`、起始时间 98880 毫秒，沿用原试验的截取范围。

模块当前进展见[回合识别说明](../README.md#当前进展)。历史试验脚本保留在 `backup/module-reorganization-20261019/backend/tests/rally_benchmark/`；旧路径与新位置的对应关系见[迁移记录](../../../backup/docs/records/module-reorganization-20261019.json)。

## 实验报告

`reports/` 保存算法比较、效果和取舍证据。先看[算法确认记录](reports/algorithm-decisions-20261019.md)，再按其中链接查找原始报告和结果。素材与人工标注的审核记录归[数据集](../../../datasets/README.md#审核与整理记录)，文件输入与实时模拟实验归[媒体模块](../../media/experiments/realtime-input.md)。

报告是当时的实验记录，不代表当前版本已通过验收。历史 JSON 保留原路径和校验值，迁移过程可查[归档的报告迁移清单](../../../backup/docs/records/report-migration-20261019.json)。

## 查看视频与结果

视频、人工标注与算法区间统一通过仓库内的 [review-video-results 技能](../../../.agents/skills/review-video-results/SKILL.md)查看。按其中的[数据格式](../../../.agents/skills/review-video-results/references/data-format.md)准备 JSON，放在所属模块的运行目录，从仓库根目录执行：

```sh
python3 .agents/skills/review-video-results/scripts/review.py \
  --data modules/rally/.runtime/本次实验/review.json --port 18770
```

打开终端打印的网址，检查实际视频和时间轴。固定模板、服务脚本、数据格式和展示规则统一在技能中维护；只在修改查看器或发现异常时执行其中的维护检查。历史实验页和原始结果保留，后续查看默认使用固定查看器。
