# OPT20 第1轮开发输出

本轮只做静态删除，没有运行模型、媒体或测试，也没有改 task/标准、生产以外的模块或 README。D-short 基线由主控已有本轮证据，本阶段未读取重算。

删除 `recognize.observe` personal 分支中的 body_features import、灰度缩放、Farneback、previous gray/time 状态及 body_motion 赋值，仅保留原有 appearance descriptor。`players_v2.follow` 的候选 cost、匹配和模板更新逻辑不变，只删所选 person 中未使用的 body_motion 复制。`trials.series` 保留 times/speed/present/ball 计算，移除 upper/articulation 数组、读取、median 及返回键；清理 median 注释。因唯一活跃 caller 已删除，删除 `modules/rally/common/body_features.py`。

静态数据流核对：此前 observe 是唯一 `body_features.body_motion` caller；follow 是唯一读取每人 `body_motion` 的生产 consumer；`trials.series` 是唯一读取并产出 upper/articulation 的 consumer。`pose_context.extract` 只使用 series 的 times 和 ball，并将其 ball 子集传入最终 signals；PyrLK 的 pose_context 计算不在修改范围。当前 `modules/rally` 活跃代码中已无 body_features/body_motion/Farneback/previous_gray/previous_time/articulation 引用。`scenarios/original-provenance.json` 中保留的是历史来源元数据，不属于活跃 consumer。README 的 D 场景说明未承诺使用全画面光流，仍描述保留的人物动作、球和脚点能力，因此无需改写。

本轮检查：对三个修改后 Python 文件用 `compile()` 做语法检查通过；`git diff --check` 通过。未运行 pytest、`pnpm run test:backend`、真实 D 候选或任何媒体/模型；这些仍待主控按串行顺序释放。尚未证明真实 D 的 selected track IDs、raw/export、person-signals 全数组等价，也未验证生产入口行为。

改动概况：4 个文件，新增/删除合计约 27 行净删除（`recognize.py`、`players_v2.py`、`trials.py` 和删除 `body_features.py`）。当前工作树起点为 task 记录的 `5bb39fa69181e86c21bde20e74d951f1cb2ca415`。

SHA256：

- `modules/rally/recognize.py`: `08f340cce19d3649705bbb5c35c42ee60047800aa4dd0d3b1a68076a9f7f976f`
- `modules/rally/common/players_v2.py`: `8d7bfc1a45b3fdbf396d491e7d26ac540863595e94cc4f6699f96066cbf3273c`
- `modules/rally/common/trials.py`: `994f9a3759cbee543fe97024e3f21e7baf4a9b7bbded1e571c2961cbbd805550`
- `modules/rally/common/body_features.py`: deleted; original file was 17 lines.

## 实际对照报告收口

基线和候选的 D-short 已由主控串行完整运行，本轮未重跑模型、媒体或测试。已读取本工作树的 `candidate-report.json`、`equivalence.json`、候选证据及正式 `summary.json`，并核对报告正文与证据结论一致：两边 raw 预测和 500 ms 导出区间均 13 项且相同；`decisions.json` 和 `person-signals.npz` SHA 相同，NPZ 的 13 个数组逐值相同；视频 SHA、输入清单 SHA、三份模型权重 SHA、7527 帧/遍与两遍解码、TrackNet/Person/Pose工作量相同。`equivalence.json` 的各项导出与媒体结构标志均通过，MP4 字节 SHA 相同。报告保留了逐项原始结果、完整数组键与维度、资源采样和两边源码 SHA。

单次 API 识别时间为基线 308.514397875 秒、候选 252.988705917 秒；报告明确这只是本样片的一次观察，不代表稳定收益。D-short 约 250.9 秒，未覆盖 30 分钟验收；无匹配人工标注，不作准确率结论。CPU/RSS/MPS 数值标作约 1 秒采样观察值。后端检查 `107 passed in 13.10s; one warning` 来自主控报告，本轮没有重跑，已在正式报告与 summary 中标明来源。

报告文件：`apps/video-clipper/reports/opt20-flow/README.md` 和 `summary.json`。本轮仅核对已有产物与补记自己的输出，没有修改生产代码、测试、baseline/candidate证据或运行模型。
