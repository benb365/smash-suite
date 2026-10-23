# OPT-09A C-short 单组找球试验

## 结论

本轮不采用 native 或 shifted 单组候选，也不改生产代码。两候选都完整处理 C-short 的 5400 帧，但区间输出相对保存的 OPT-07A 双组控制发生变化；当前没有 SHA 匹配的人工标签证明改变保留了目标效果，因此按授权规则保守不采用。这个判断只覆盖本次 C-short 候选。

## 结果入口

- [机器可读汇总](summary.json)：完整 raw/export 区间、并集差异、诊断、计算量、运行环境、代码和输入/权重来源 SHA。
- [查看器数据](review.json)：实际视频与三组实际输出，缺少人工 truth 行；差异窗口仅用于定位。
- 主控播放了 6.018–12.020 秒，三条时间轴同步；点击双组时间轴 8.135 秒时，界面显示 dual/native 保留而 shifted 删除。这只是局部差异定位，不是完整视频复核或人工回合标注。
- 原始截图：[viewer.png](viewer.png)；SHA256 `297f2654578570d55fc15443424ba9f2d46b61253e29d891c9fe52a0452bafef`。截图逐字节复制自 primary runtime。

| 方案 | 识别墙钟 | TrackNet 调用 / 输入帧 | cache miss / hit | 输出回合数 |
|---|---:|---:|---:|---:|
| OPT-07A 双组保存控制 | 97.745 s | 3599 / 10797 | 5400 / 5397 | 9 |
| OPT-09A native 单组 | 53.246 s | 1800 / 5400 | 5400 / 0 | 10 |
| OPT-09A shifted 单组 | 52.132 s | 1801 / 5403 | 5400 / 3 | 8 |

单组两次都选择 900 张人物图、225 次人物检测调用、7170 个框；选中人物与双组控制相同。两候选 people feature SHA 相同，最终选中帧 ID 为 0–5399 且 PTS 相同。双组 97.745 秒来自另一轮已保存运行，不是本轮重跑或稳定性能结论。

## 输出变化

所有差异都是算法区间并集差异，不是已确认漏失、误报或准确率。native 相对双组 raw 少 5300 ms、多 10768 ms；导出区间（padding 500 ms）少 5300 ms、多 11768 ms。它新增 105.6–115.667 秒区间。shifted raw 少 3167 ms、多 2900 ms；导出少 4167 ms、多 2900 ms。shifted 没有保留原双组 7.7–10.8 秒首段，并将 91.5–103 秒区间延长到 105.9 秒。

单组 wall time 与采样资源来自每个候选的一次运行。采样约每秒一次，峰值不是连续监测；不同轮次的单次观察不能证明稳定收益。双组保存镜像没有逐窗口预测点，因此本报告不做逐点对照；候选实际逐帧 observations 保留在 runtime 证据目录，不复制进报告。

## 复核窗口

使用仓库固定视频查看器打开 [review.json](review.json)，检查 6–12 秒、39.5–46 秒和 103–117 秒。窗口名称只说明算法输出不同，不暗示人工判断。

## 证据来源

- 候选原始证据：`apps/video-clipper/.runtime/opt09a-single/C-short-native/` 与 `C-short-shifted/`。
- 双组控制：主目录已保存镜像 `apps/video-clipper/.runtime/opt07a/recognition/candidate/C-short/`，按 preservation 清单核验 SHA；未在本轮重跑。
- 代码基线 commit：`c62527982a6bcd6fc95cb00572f346d52d36fffb`。recognize SHA `17fb4cfb4387a8394836bc9793e526c42cf139ec291d6ee890a9d09e7052adad`；原 predictor SHA `d8208470e973ff4388d8c34be54f19609a50a61571e72aaa3ed45dcaf8c34152`。
- 结果、各运行代码/权重/输入 SHA 及资源摘要见 [summary.json](summary.json)。
