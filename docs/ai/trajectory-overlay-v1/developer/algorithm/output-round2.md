# 算法开发输出 · 轮次2

## 当前状态

轮次2代码、两源真实离线结果和报告已冻结；交付后停止修改。没有运行 TrackNet、YOLO 或下载，没有修改产品实现和其他角色目录，没有提交。

工作树：`/Users/bytedance/.codex/worktrees/trajectory-overlay-v1/smash-suite`。正式报告：`modules/trajectory/reports/trajectory-overlay-round2.md`；模块入口 `modules/trajectory/README.md`。轮次1输出归档在本目录 `output-round1.md`，round1证据未覆盖。

## 本轮修改文件

- `modules/trajectory/analyzer.py`：现有日志行数/末时间完整性校验；蹲身尺度修正；停滞球点连续分段拟合；缺口接触恢复及来源/时间区间；不跨缺口删除真实后续同侧事件；长未知区间清除旧箭头。
- `modules/trajectory/tests/test_trajectory.py`、`real-observation-regressions.json`：完整meta+截断文件、末时间不符、A1/A2实际缓存分拍及未知段回归。
- `modules/trajectory/README.md`、`reports/trajectory-overlay-round2.md`；首轮报告只加当前报告入口。
- 自己的通信输出。未改相机、日志生产端或产品时间逻辑。

## 真实返工结果

A1：恢复缺口中的远端接触估计25.44秒（可能区间25.16–25.56），保留26.32秒近端转折（26.36附近实际球点支持）。24.64–28.48不再是一条3.84秒近端箭头：

- 24.64–25.20 near；25.20–25.44 unresolved。
- 25.44–26.32 far；26.32–26.64 near。
- 26.64–28.48 unresolved，随后28.48 far。

A2：恢复74.32远端、75.24近端；75.84的远端回球是缺口后重现推断，可能接触区间75.24–75.84。76.12在可达范围内利用相邻回球方消歧为near。75.28–75.84单列unresolved，不维持旧近端箭头。

上述是具体观测与推断，不是精确逐拍人工真值。A1 26.8–27.5有远端动作但球点长缺失，无法确定接触时刻，本轮未造一拍；清除旧箭头后仍需独立复核。A2 76.12–78.96仍有分拍完整性风险，报告已列明。

## 新统计

独立未知段也在 `shots` 中，因此段数不能当拍数：

| 样本 | 触球事件 | 区间段 | predicted | next_hit | detected | unresolved |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 37 | 41 | 15 | 17 | 3 | 6（4独立未知段） |
| A2 | 25 | 27 | 11 | 12 | 1 | 3（2独立未知段） |

每源结果仍在 `modules/trajectory/.runtime/<样本目录>/shot-paths.json`；未改写球点/人物缓存。新证据为 `modules/trajectory/.runtime/round2-evidence.json`，包含代码/球点/人物/结果SHA、源SHA、逐回合数及返工窗口逐段诊断。

## 验证与命令

在本任务worktree根目录，分别对两个已冻结样本运行原 `modules.trajectory analyze` CLI，使用现有 `ball-observations.jsonl`、`rallies.json` 和权重目录 `/Users/bytedance/workspace/experiments/smash-suite/.runtime/product-data/models`；两份均退出0，未运行模型。完整命令见正式报告。

```sh
.venv/bin/python -m pytest modules/trajectory/tests modules/rally/tests -q -p no:cacheprovider
git diff --check
```

最终77项测试通过，差异检查通过。原有50.28漏点、79.88/84.80假击球、A1末尾落地、终点优先、下一拍帧隔离回归保留通过。合成数学/mock仅检查工程行为；真实效果依据保存观测与原片，未冒充人工验收。

原片复核：直接看转交的 `/tmp/trajectory-independent/{a1,a2}-window-1.jpg`，并解码保存本模块 `.runtime/<样本>/round2-frames-*.jpg`。没有读取verifier目录或另造HTML。

按统一技能启动查看器：

```sh
python3 .agents/skills/review-video-results/scripts/review.py \
  --data modules/trajectory/.runtime/review-round2.json --port 0
```

当前地址 `http://127.0.0.1:52192/`，服务 session 59774。当前工具没有可用浏览器（inventory browsers=[]），所以本轮未完成网页播放/切换复核；主控可打开入口。数据与服务已准备好。

## 冻结摘要与后续

算法代码摘要：`ca2c28391b0aba07f776db0a257c0fb0f4402eaad05d71fd39ba34ace0e14d9e`。

- A1 新结果 SHA256：`7e0302f5b8680bc35a8585726977e03b873eb31645ec2389302f7ed3b4296519`。
- A2 新结果 SHA256：`1782cc3e81fd87d9cc8d28c4bf2badb0a0d49241c806d403d65c1a1ae959d0a3`。

接下来由主控安排复用缓存重新烧录和独立验收。特别检查上述未知段是否清除旧箭头、已恢复真实方向和A2后续空间重叠段。未宣称功能验收通过；交付后不再修改代码。
