# 输出核对脚本准备

本角色已准备独立核对脚本 `validate_outputs.py`。脚本计划核对 10 份输出：6 项正式测量、原有 3 项 stats OFF 剖析，以及新增的 `profile-native-A/A-short` 原生补录。每份均检查运行状态、MPS/balanced 配置、预测和导出区间、区间时长与 worker `output_duration_ms`（仅允许浮点精度误差）、产品阶段计时、输出 SHA、完整音视频解码、PyAV 逐帧尺寸与 PTS、容器/视频/音频时长、统计/MPS 样本和资源进程树。解码尺寸会与 `outer.state.video.width/height` 明确比较；MPS 有效证据要求至少一条 `allocated_bytes > 0` 的样本。资源核对计算 runner 汇总 PID 与原始采样 PID 的差集，并保留采样间隔和错误。

执行时，脚本会在 `apps/video-clipper/.runtime/performance-baseline/output-validation/` 下创建带时间戳的结果目录，逐项保存 `validation.json` 和 FFmpeg 解码日志。失败时保留已产生的诊断并返回非零。输出时长与导出区间时长的差值只记录，交由主控判断；不会以该差值擅自判失败。

新增补录会与 `baseline/A-short` 再做一次严格对照，并保留原 `profile-A/A-short` 对照；每组都比较原始 `predictions`、`export_ranges` 和成片结构/解码帧数。补录 `native-A-report.json` 作为必需报告检查存在性，不把补录耗时纳入基线。编码文件 SHA 分别核对各自 runner 归档值，不要求 ON/OFF 两份成片字节相同。区间时长误差用 `rel_tol=1e-12`、`abs_tol=1e-9 ms` 作为浮点表示容差，其他容器和流时长只记录供主控判断，不设置额外宽松阈值。

`validate_outputs.py` 本轮只做语法编译检查，未读取 10 份处理输出、运行测试、解码视频、计算成片 SHA 或运行输出核对。

## A 的 py-spy 火焰图摘要

按新增授权，新增 `python_profiles.py`，参数要求显式传入 `--cases A/C/D`。本轮只解析已保存的 A SVG 和 `py-spy.log`，摘要写入 `apps/video-clipper/.runtime/performance-baseline/python-analysis/A/summary.json`；未处理 C/D，也未执行 10 份输出核对。

A SVG 为 108,520 bytes，SHA256 `7619ac0cb1298c480a52193841c00a47d83bbe991482bdecdb94c81be29f7aa8`；py-spy log 为 432 bytes，SHA256 `49c74557d7a299e9cfa26123a3d985f459b50b99b180901734b8ce435b0274ee`。log 记录 17,532 collected、0 errors；SVG `total_samples=17,508`，少 24。两个采样口径均原样保存，未假设相等或改动输入。

SVG 中 `recognize (modules/rally/recognize.py:59)` 覆盖 4,210 samples，占 SVG 全量 24.05%；以 4,210 为识别子树分母。该函数 self 为 1 sample。区间并集合并后，识别子树内 `rally_stream.process` 为 4,209 inclusive / 21 self，`tracknet_rally.process` 为 4,188 / 11，TrackNet predictor `__call__` 为 4,177 / 1,194；`tracknet.model.forward` 为 2,126 / 43。具体行号、库调用及前 30 帧的 inclusive/self 数量在 JSON 中。修正后的脚本按 `modules/rally/recognize.py` 中精确函数名匹配 `observe` 和 `person_signals`；A 中仍无这两项的栈帧。Pose 按 `modules/models/keypoint_rcnn.py` 及当前 checkout 的实现文件 `modules/models/keypoint_rcnn/__init__.py` 精确匹配；A 中无 Pose 栈帧，不把缺少采样覆盖解释成零耗时。

A handshake 等待已用 SVG 的 `main (app/worker.py:52)` 栈帧单独计量：10,427 samples，占 SVG 总样本 59.56%。已核对当前冻结源文件 `apps/video-clipper/backend/app/worker.py:52` 为 `time.sleep(.05)`；该区间与 `recognize` 的 4,210 samples 相交数为 0。等待帧不进入算法热点结论，samples/rate 不换算等待墙钟；完整等待时长应取 benchmark-clock `profile_ready` 到 `benchmark_start`。上一版“SVG 未包含 wait/handshake 栈帧”的结论有误，旧结论和更正依据保存在 `python-analysis/A/summary-correction-diagnostic.json`，新摘要已重解析覆盖为正确映射。所有样本只代表栈驻留，不等价于纯 Python CPU 时间。修正后脚本语法编译和 A 实际 SVG/log 解析通过；本轮未启动模型或采样器，也未解码 10 份输出。

## 实际核对结果 v2（2026-10-21）

输出核对报告：`apps/video-clipper/.runtime/performance-baseline/output-validation/run-20261021T024238Z/validation.json`。本次用仓库现有 `.venv`（PyAV 14.2.0）运行，报告 `passed`，共 10 项、0 issues。初次用系统 Python 的报告因无 PyAV而失败，已留在 `output-validation/run-20261021T024200Z/validation.json`，未覆盖；之后已用项目环境完成全量检查。

10 项均 `completed`，baseline/profile 类型与 statistics 开关符合预期；10 个归档 SHA 全部匹配，FFmpeg 完整 AV 解码 exit 0，PyAV 帧尺寸均为 1920×1080 且等于 `outer.state.video`，PTS 单调且音轨存在。所有 worker `output_duration_ms` 与 `sum_ranges_ms` 的差值都是 0.0 ms；三阶段计时和总耗时差都是 0.0 s。六正式输出均有至少一条 `allocated_bytes > 0` 的 MPS 样本，资源树均覆盖 backend/worker/FFmpeg，runner PID 差集为空、资源错误为 0。样本间隔超过 1 s 的数量及最大值保留如下；这是观察值，不额外作为失败阈值。

| 输出 | 帧数 | worker / ranges / 差值 (ms) | 容器 / 视频 / 音频时长 (s) | 容器−视频 / 容器−音频 (s) | MPS有效/总样本 | >1 s间隔数 / 最大间隔(s) |
|---|---:|---:|---:|---:|---:|---:|
| baseline/A-short | 1,161 | 46,440 / 46,440 / 0 | 46.44 / 46.42 / 46.44 | 0.01999999999999602 / 0 | 37/38 | 47 / 1.0194410840049386 |
| baseline/A-long | 6,445 | 257,800 / 257,800 / 0 | 257.8 / 257.78 / 257.8 | 0.020000000000038654 / 0 | 200/201 | 243 / 1.0230426250491291 |
| baseline/C-short | 3,326 | 110,867 / 110,867 / 0 | 110.867 / 110.867 / 110.867 | 0 / 0 | 115/116 | 135 / 1.0263515419792384 |
| baseline/C-long | 8,438 | 281,623 / 281,623 / 0 | 281.623 / 281.623 / 281.6219954648526 | 0 / 0.0010045351473877417 | 516/517 | 576 / 1.0285644170362502 |
| baseline/D-short | 4,413 | 147,100 / 147,100 / 0 | 147.1 / 147.1 / 147.1 | 0 / 0 | 318/319 | 329 / 1.02494562510401 |
| baseline/D-long | 9,211 | 307,211.625 / 307,211.625 / 0 | 307.211625 / 307.211625 / 307.211 | 0 / 0.0006250000000136424 | 829/830 | 869 / 1.0270020000170916 |
| profile-A/A-short | 1,161 | 46,440 / 46,440 / 0 | 46.44 / 46.42 / 46.44 | 0.01999999999999602 / 0 | — | 184 / 1.026973375119269 |
| profile-C/C-short | 3,326 | 110,867 / 110,867 / 0 | 110.867 / 110.867 / 110.867 | 0 / 0 | — | 165 / 1.0259833328891546 |
| profile-D/D-short | 4,413 | 147,100 / 147,100 / 0 | 147.1 / 147.1 / 147.1 | 0 / 0 | — | 444 / 1.0270393749233335 |
| profile-native-A/A-short | 1,161 | 46,440 / 46,440 / 0 | 46.44 / 46.42 / 46.44 | 0.01999999999999602 / 0 | — | 52 / 1.0300872921943665 |

统计 ON/OFF 三组及 A 原生补录对照均严格一致：

| baseline 与 profile | predictions | export_ranges | 输出结构/帧数 | 差异 |
|---|---|---|---|---|
| A-short / profile-A | 相同 | 相同 | 相同（1,161帧） | 无 |
| C-short / profile-C | 相同 | 相同 | 相同（3,326帧） | 无 |
| D-short / profile-D | 相同 | 相同 | 相同（4,413帧） | 无 |
| A-short / profile-native-A | 相同 | 相同 | 相同（1,161帧） | 无 |

资源采样原始缺口汇总已保存于上述 JSON；10 项的资源错误数均为 0，PID 未采集差集均为空。C/D Python 摘要及输入 SVG/log 的路径、大小和 SHA 已保存于 `python-analysis/C/summary.json` 和 `python-analysis/D/summary.json`。C SVG total 为 22,631，log collected 为 22,667（差 −36），log 报 2 次同一线程 8411946624 的 `get_stack_trace` 展开失败；对应原始 warning 已逐条留在摘要，底层原因未证实。C 有 `recognize` 覆盖 12,179 samples（53.82%）、`observe` 11,540、TrackNet predictor 9,261；没有 `person_signals` 或 Pose 栈帧。故 C 状态为 `passed_with_sampling_errors`，表示有效但局部缺失，供独立验收判断证据充分性；错误不按样本总差值折算缺失率。原 failed 状态和更正规则保存在 `python-analysis/C/summary-correction-diagnostic.json`。D SVG total 为 46,137，log collected 为 46,153（差 −16），log errors 为 0；原始 Inferno warning “Ignored 1 lines with invalid format” 也保留。D `recognize` 覆盖 32,199 samples（69.79%）、`observe` 14,000、`person_signals` 17,982、Pose 16,058、TrackNet predictor 6,499。C/D 的热点覆盖只按 `recognize` 子树和区间并集解释，不以 samples/rate 推墙钟或纯 Python CPU 时间。

输出核对按实测容器、视频、音频时长逐项保留原值，不额外引入时长宽容阈值。基线与剖析结果只证明本次 10 项及三组短片等价检查通过；C 的 Python 采样错误和 SVG/log 样本口径差异仍是后续独立验收需评估的限制。
