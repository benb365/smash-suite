# 算法开发输出 · 轮次3

## 冻结状态

本轮实现和两源离线结果已冻结，交付后停止修改。唯一工作树 `/Users/bytedance/.codex/worktrees/trajectory-overlay-v1/smash-suite`；不提交。没有运行 TrackNet/YOLO、下载或修改产品/媒体实现，没有读取其他角色通信目录。

报告：`modules/trajectory/reports/trajectory-overlay-round3.md`。完整证据：`modules/trajectory/.runtime/round3-evidence.json`。原帧全回合审查：`round3-event-audit.json` 及两源 `round3-audit/*.jpg`。轮次2输出归档 `output-round2.md`，旧证据未覆盖。

## 修改与真实结果

修改 `modules/trajectory/analyzer.py`、测试与真实观测fixture、模块README、轮次3报告；轮次2报告只加历史/当前入口。删除弱重现补拍和交替改写归属；限制候选簇总跨度，运动证据一致者优先；独立同侧真实转折保留但缺失对手时刻仍未知，中间停滞不称落地。

F2：A2 76.1 秒 far → 78.00 near → 78.96 far；无75.84伪触球、无76.52–76.72新增事件。已看完整画面与真实点。七回合均有原帧检查，恢复 A1 107.4/108.1网前、149.16/150.1尾段转折，并把150.40抖动候选换为151.12远端真实扑球。未知区间仍明确不算拍。

| 样本 | 触球 | 区间 | predicted | next_hit | detected | unresolved |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 42 | 49 | 24 | 11 | 3 | 11（7 段无起点） |
| A2 | 25 | 26 | 11 | 12 | 1 | 2（1 段无起点） |

两源输出位于 `modules/trajectory/.runtime/<样本>/shot-paths.json`。复算CLI均退出0，命令见正式报告；模型调用0，原球点/人物缓存摘要与前轮一致。触球时间是估计，非人工标注。

## 验证

- 算法/回合：81 passed。
- 最终直接 pytest 全集：127 passed，1 项既有 Starlette 弃用提示。
- `pnpm run test:backend` 已执行但包装先安装依赖，在约定 node_modules 符号链接处失败；未改依赖，直接运行同脚本 pytest 作等价检查。
- `git diff --check`：通过。
- 浏览器工具先前确认无可用浏览器，因此不声称网页播放验收。标准技能数据 `modules/trajectory/.runtime/review-round3.json` 已准备；查看器地址 `http://127.0.0.1:55849/`（session 64104）。原片复核使用实际解码帧，不另造HTML。

## 摘要与后续

算法代码摘要 `93241c7828967273216b6b78f55ce36131813192b9f0ba84bfeb15b5905100f8`。

- A1 结果 `b526b4f0e221c55d9bf7cc7a69532fa4d9791135c8102f7afee52e95215b6505`。
- A2 结果 `8525aeeb5bf57e07d746b34efef43994846e36993a53f908fe40fe7ce981aeb9`。

剩余由主控安排当前结果重新烧录与独立验收。未宣称功能或量化精度验收通过；本角色交付后停止。
