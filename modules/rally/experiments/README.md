# 回合识别实验入口

在仓库根目录、共同 Python 3.9+ 环境中使用。

- `python -m modules.rally`：从视频运行当前场景方案，详见[模块说明](../README.md)。
- `python -m modules.rally.experiments.run_live_tracknet --video ... --output ...`：文件原速输入诊断；可用 `--mode offline` 尽快读取。
- `python -m modules.rally.experiments.run_tracknet`：早期恒定帧率基线诊断，具体参数见源码或 `--help`。

当前自动测试使用合成输入，真实识别从视频入口运行。旧16例保存观测检查依赖的35份缓存现已缺失，其专用入口和清单已移除，不作为当前验证方式。历史取舍仍可查本目录 `reports/`，人工标注仍位于 `datasets/`。本次性能任务使用三份真实短片作统计开关对照，要求见[性能基线协议](../../../apps/video-clipper/reports/performance-baseline.md)。

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
