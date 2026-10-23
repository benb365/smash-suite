# 算法开发输出 · 轮次1

## 交付状态

已完成本轮算法实现与两份真实缓存离线复算；代码冻结，可用于产品联调。尚未完成产品成片独立验收，且保留长漏点导致漏拍的明确缺口，不能标记全量逐拍效果通过。

唯一开发/执行 worktree：`/Users/bytedance/.codex/worktrees/trajectory-overlay-v1/smash-suite`。没有另建 worktree，没有提交，没有访问或修改其他角色通信目录，没有重跑 TrackNet。

正式说明：[模块 README](../../../../../modules/trajectory/README.md)；[算法报告](../../../../../modules/trajectory/reports/trajectory-overlay-v1.md)。

## 当前实现与文件

- `modules/trajectory/observations.py`：context manager 真实球点日志、低分坐标空值、源/权重哈希与完成状态。
- `modules/trajectory/capture.py`、`__main__.py`、`__init__.py`：独立采集及冻结球点重算 CLI、导出接口。
- `modules/trajectory/court.py`：12 帧中值白线标准模板自动标定；地面与网带证据分离；方形像素/中心主点假设下，用真实网带高度和地面几何共同拟合一致欧氏相机，取消伪造同 x 网柱。
- `modules/trajectory/analyzer.py`：复用真实 YOLO 缓存、人物关联、逐拍转折、重力/平方速度阻力拟合、接球人物软约束、实际落地优先、替代和未解析诊断。本模块不反向依赖 rally 实现。
- `modules/rally/recognize.py`、`tracknet_rally.py`、`scenarios/high.py`：此前已实现的可选观测出口，原回合算法参数与判断保持不变。
- `modules/trajectory/tests/test_trajectory.py`、`real-observation-regressions.json`：相机数学、真实漏点/假击球/落地回归、终点来源优先和下一拍帧隔离。
- `modules/rally/tests/test_tracknet_rally.py`：观测出口和日志生命周期回归。
- `modules/trajectory/README.md`、`reports/trajectory-overlay-v1.md`：调用、复现、实际统计、具体失败案例和边界。

恢复补充均已处理：白线支持比例正常；相机由真实地面/网带一致约束；末拍可见落地优先；短发球线 4.72/8.68；不复用旧 court 缓存；通过拟合的接触起点写 `start_source`，脚点代理另记来源；拟合不包含下一击球帧。

## 真实输入与当前输出

源：`datasets/badminton-v1/local/rally/<下列目录>/clip.mp4`。

| 样本目录 | 原始球点 | 人物帧 | 回合/拍 | predicted | next_hit | detected | unresolved |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `m1-short-a1-01-20261015` | 4200 行，1249 有效 | 1400 | 5 / 35 | 14 | 16 | 4 | 1 |
| `m1-a2-01-20261019-workerfix` | 2421 行，1022 有效 | 807 | 2 / 23 | 11 | 10 | 1 | 1 |

每份缓存/输出目录：`modules/trajectory/.runtime/<样本目录>/`；内有 `preflight.json`、`ball-observations.jsonl`、同名 meta、`rallies.json`、`people-observations.json`、`court.json`、`court-calibration.jpg`、`court-line-mask.png`、`player-tracks.json`、`shot-paths.json` 和原帧诊断 `contact-*.jpg`。

当前冻结代码/源/模型/输出 SHA 和逐回合统计：`modules/trajectory/.runtime/round1-evidence.json`。正式报告保留关键 SHA；其中 analyzer 为 `c1b8c8bf...`，court 为 `42dc1583...`。当前方法版本为 `temporal-median-white-lines-standard-template-v2` / `square-pixel-centered-principal-point-floor-and-net-v2`。

## 执行与验证

均从上述 worktree 根运行：

```sh
.venv/bin/python -m modules.trajectory analyze \
  --video datasets/badminton-v1/local/rally/SAMPLE/clip.mp4 \
  --observations modules/trajectory/.runtime/SAMPLE/ball-observations.jsonl \
  --rallies modules/trajectory/.runtime/SAMPLE/rallies.json \
  --output modules/trajectory/.runtime/SAMPLE \
  --weights-dir /Users/bytedance/workspace/experiments/smash-suite/.runtime/product-data/models
.venv/bin/python -m pytest modules/trajectory/tests modules/rally/tests -q
git diff --check
```

两份 CLI 均退出 0；测试 71 passed，仅 pytest 缓存目录的默认沙箱写权限提示；差异空白检查通过。后续单独 trajectory 复验 6 passed。没有下载新模型或依赖。

素材 skill 已读；wrapper status 因系统 Python 3.9 / 本 worktree 技能 venv 写限制失败后，用既有 Python 3.11 直接运行同技能 `scripts/curate.py status`、`rally-status` 成功，读取缓存和长期决策，没有搜索或下载素材。

按仓库 `review-video-results` 技能准备实际保存数据并启动：

```sh
python3 .agents/skills/review-video-results/scripts/review.py \
  --data modules/trajectory/.runtime/review.json --port 0
```

当前只读查看器 `http://127.0.0.1:54363/`，服务 session 2510。已在后台浏览器检查 A1 真实画面播放、8 秒问题定位及切换 A2 后的 49 秒时间轴；标签页已保留。子代理不支持设为可见，主控可打开同一网址展示。没有另造 HTML。

## 真数据与模拟边界

真实证据是冻结 TrackNet / YOLO 观测、视频原帧、自动标定叠图和离线结果。合成相机只检查数学恢复；mock 测试只检查帧隔离与来源优先级。都不作为真实精度证据。

预计落点用下一击球者位置作软约束后，再物理外推到地面；不是简单把下一击球脚点重命名为预测。重投影残差低不证明落点准确。模型可输出场外坐标，无裁界掩盖。

## 已知缺口与下一步

- A2 73.92–76.12 秒仍可能合并多拍：中间 400 / 600 ms 缺口，仅一近端球点，当前拒绝拟合并 next_hit；A1 24.64–28.48 秒同样有长漏点合并风险。没有放宽阈值补造精确 hit。
- A1 108.72 秒尾拍只有两点、A2 87.16 秒末拍物理残差约 193 px，均 unresolved。
- 人物脚点、击球时刻、自动落地与中心主点是假设/估计；镜头移动、双打、其他机位未验收。
- 当前代码可供真实 worker/API/MP4 联调，接着由独立验收观看连续回合、输出球场方向及上述缺点区间。若验收判为明显错误，按实际问题继续修复，不能凭 25 个 predicted 计数宣称验收完成。
