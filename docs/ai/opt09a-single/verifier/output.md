# OPT09A 第1轮独立验收

## 结论

| 范围 | 结论 | 依据 |
|---|---|---|
| 功能 | 通过 | 独立 shifted 完整运行与冻结结果的 5400 条 observations、frame ID、PTS、1801 个模型窗口、人物特征 SHA、选人及预测/导出区间逐值一致；6 项边界检查通过。 |
| 代码 | 通过 | 当前实现只在实验 runner 中派生替换 `observe` 的一次分支，并绑定当前生产函数；9/10/11 帧覆盖真实尾帧，1/2 帧不造三帧组。生产代码 SHA 与冻结记录一致。 |
| 文档与证据 | 通过，限于本轮范围 | 报告对照和保守不采用结论与原始证据相符；冻结文件及列出的代码、报告和已有运行证据 SHA 均未变化。固定 viewer 的播放与截图记录来自主控冻结证据，本验收未独立再次播放。 |

## 独立重跑与证据核对

- 工作树 HEAD 始终为 `c62527982a6bcd6fc95cb00572f346d52d36fffb`；`acceptance-freeze.json` SHA 始终为 `c967603b5d62d11ab4997256ddbc488a778ae490e24d16d533ada501f60d0b27`。冻结清单中的文件及旧 runtime SHA 全部匹配。
- 按冻结命令在实际 MPS 上完成 shifted C-short 一次：5400 帧解码并交付，首末 PTS 为 0.0/179967.0 ms；选中 ID 覆盖 0–5399，最终两条下游流相同。TrackNet 1801 次、5403 输入帧、5400 miss/3 hit；人物检测 900 张/225 次。输出、选人和逐窗口数据与冻结 shifted 结果相同。复跑识别耗时约 52.14 秒，冻结运行约 52.13 秒；耗时差异属于单次测量波动。
- native 冻结证据也核对到 5400 帧完整 EOF、1800 次/5400 输入、选中 ID/PTS 全覆盖、900 张人物图/225 次调用。shifted 的统计中 `native_observations=3` 是内部计数；最终选择流仍有 5400 条，未丢帧。
- 首组三帧为 `[0,1,2]`，末组三帧为 `[5397,5398,5399]`；实际窗口含 frame ID、PTS、预测点和候选数。原始 observations 不含新增 phase 字段。把实际选中流传给现有 `observed_candidates(rows, rows)` 重算后，两边均为 5400 帧，保留候选的 phase 标签均为 0，符合相同输入去重及第一流来源语义。
- 使用现有 `docs/ai/opt08a-size/summarize.py` 区间并集函数独立重算，报告数值一致：native raw 缺 5300/增 10768 ms、export 缺 5300/增 11768 ms；shifted raw 缺 3167/增 2900 ms、export 缺 4167/增 2900 ms。shifted 删除双组首段 7700–10800 ms。它们是算法输出差异，缺少 SHA 匹配 truth，不能据此判定准确率或真实漏球。
- 本验收未运行另一遍 dual；它仍是 preservation 清单匹配的 OPT-07A 主目录镜像，不作为本轮新跑或稳定性能结论。没有新增产品修改，因此无需后端、前端或生产验收。报告里的局部 viewer 复看依据为主控已有播放/截图记录；未声称独立视觉复核。

## 执行记录

- `.venv/bin/python -m pytest docs/ai/opt09a-single/test_experiment.py -q`：6 passed；pytest 缓存目录不可写产生一条 warning，不影响结果。
- `git diff --check`：通过。
- 仅新增本文件和独立 runtime 结果 `apps/video-clipper/.runtime/opt09a-single/independent-C-short-shifted/`；未改实现、正式报告或验收标准，未暂存、提交或推送。
