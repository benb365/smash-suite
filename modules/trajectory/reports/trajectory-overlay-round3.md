# 二维球路轮次3返工报告

## 结论与入口

本轮已修复弱缺口推断改写真实击球方、同侧贪心过滤吞拍和候选串联成过长簇的问题。两源冻结观测离线复算完成，代码与结果冻结，等待独立成片验收；尚未宣称逐拍完整性或落点精度通过。

A2 原片 76.16–76.28 秒远端低手出球现归远端，约 78.00 秒近端回球保留；75.84 秒仅重新出现不再算触球，也没有增加 76.52–76.72 秒事件。完整数据见 `modules/trajectory/.runtime/round3-evidence.json`，逐回合原帧清单见 `round3-event-audit.json`，统一技能查看器数据为 `review-round3.json`。

## 通用机制修复

- 删除仅由缺口后重新出现建立的对手触球，以及基于交替关系改写人物归属的分支。直接触球位置证据优先于缺口弧线推断。
- 候选簇以首候选限制总跨度，避免相邻候选连锁吞掉真实接触。局部顶点与两侧运动方向一致的证据优先于孤立抖动。
- 连续分段曲线支持的独立同侧转折可以保留；两个局部窗口不重叠用于判断证据独立，不是预设拍频。缺少中间对手触球时刻时，寻找对手可达观测截断旧箭头并明确未知，不补造交替事件。
- 可见落地只用于最后一拍，避免同侧事件间的中间停滞被误称落地。保留轮次2缓存行数/末时间检查、人物尺度、停滞球和缺口恢复。

本轮未修改相机、物理落点模型、产品或媒体时间映射，没有运行 TrackNet、YOLO 或下载。

## 全部回合原片核对

检查两源所有七回合的击球候选原帧，叠加前后各 240 毫秒真实球点；较长飞行及最后一拍另取每 400 毫秒原帧检查。共保存 18 张诊断拼图，位于 `.runtime/<样本>/round3-audit/`。这些是原片诊断图，不是另建的视频网页或人工标注。全部事件的实际归属与无交替偏好的最近可达人物一致；该一致性不等同于人工精度验收。

| 样本 / 原回合编号 | 触球事件 |
| --- | --- |
| A1 / 1 | 6 |
| A1 / 3 | 6 |
| A1 / 4 | 9 |
| A1 / 6 | 11 |
| A1 / 7 | 10 |
| A2 / 3 | 6 |
| A2 / 5 | 19 |

实际变化：

- A1 25 秒附近远端隐藏接触与 26.3 秒近端真实回球继续保留，26.64–28.48 秒长缺口仍未知。
- A1 网前 107.40、108.1 秒附近近端转折不再因漏掉对手而被吞掉；中间无可靠对手时刻的部分未补拍。
- A1 最后回合恢复 149.16 秒远端与 150.1 秒近端；原 150.40 秒抖动候选被约 151.12 秒远端扑球转折取代，两种运动证据共同支持。
- A2 74.32 秒远端和 75.24 秒近端仍保留，76.1 秒远端→78.00 秒近端→78.96 秒远端连续分开。76.52–76.72 秒球已升高，不当作新触球。
- 其余回合及尾段检查未再保留本轮发现的同类明显吞拍；长出画、缺少支持的段仍显式未知。

## 来源统计

独立未知段包含于 `shots`，区间数不等于拍数；统计来自最终离线结果，不代表人工真值。

| 样本 | 触球 | 区间 | 预计落点 | 下一击球替代 | 可见落地 | 未解析 |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 42 | 49 | 24 | 11 | 3 | 11（7 段无起点） |
| A2 | 25 | 26 | 11 | 12 | 1 | 2（1 段无起点） |

轮次1/2证据保留。真实球点、人物缓存与源哈希未改写；两源分别 4200、2421 行。

## 复现与验证

在 `/Users/bytedance/.codex/worktrees/trajectory-overlay-v1/smash-suite` 执行，`SAMPLE` 分别取 `m1-short-a1-01-20261015`、`m1-a2-01-20261019-workerfix`：

```sh
.venv/bin/python -m modules.trajectory analyze \
  --video "datasets/badminton-v1/local/rally/$SAMPLE/clip.mp4" \
  --observations "modules/trajectory/.runtime/$SAMPLE/ball-observations.jsonl" \
  --rallies "modules/trajectory/.runtime/$SAMPLE/rallies.json" \
  --output "modules/trajectory/.runtime/$SAMPLE" \
  --weights-dir /Users/bytedance/workspace/experiments/smash-suite/.runtime/product-data/models
.venv/bin/python -m pytest modules/trajectory/tests modules/rally/tests -q -p no:cacheprovider
.venv/bin/python -m pytest -q -p no:cacheprovider
git diff --check
python3 .agents/skills/review-video-results/scripts/review.py \
  --data modules/trajectory/.runtime/review-round3.json --port 0
```

81 项算法/回合测试通过。`pnpm run test:backend` 被宿主包装的依赖安装步骤拦住：已约定的 node_modules 符号链接不是其要求的真实 hoist 目录；未改变依赖布局。直接执行其 pytest 全集作为等价检查，127 项通过，1 项既有 Starlette 弃用提示；`git diff --check` 通过。合成数学/mock只验证工程行为；新增真实观测回归覆盖 F2 归属、78秒回球、推断高分不能覆盖直接接触、独立同侧转折与 A1 尾段抖动，不作为人工视频验收。

## 验收边界

击球时间仍是观测推断，裁取窗口可能选择相邻一帧，隐藏接触有更宽时间区间；逐拍箭头仍需独立连续观看成片。未知段不算触球。两源均为调试样本，没有独立数据集或落点真值。

本轮复核使用保存原帧和球点，未进行网页播放验收或新产品API全流程；需主控用当前结果重新导出成片。统一查看器数据已准备，当前地址 `http://127.0.0.1:55849/`；浏览器工具无可用浏览器，网页播放检查未执行。

<details>
<summary>冻结摘要</summary>

算法代码摘要：`93241c7828967273216b6b78f55ce36131813192b9f0ba84bfeb15b5905100f8`。

- A1 源 SHA256：`e2ea56c398507cc0c1679088121f26ac5a0d6b23ad12502151fb855b13966ef2`；结果 SHA256：`b526b4f0e221c55d9bf7cc7a69532fa4d9791135c8102f7afee52e95215b6505`。
- A2 源 SHA256：`0ae60f5564e9fed6058c87cdc573b5a07d5e4d8ef6137245b67f59ede5d0edc9`；结果 SHA256：`8525aeeb5bf57e07d746b34efef43994846e36993a53f908fe40fe7ce981aeb9`。

逐文件代码、源模型、球点、人物及结果摘要在 `round3-evidence.json`。该文件和原帧事件清单共同固定本轮结果，旧轮次证据未覆盖。

</details>
