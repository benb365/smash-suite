# 真实短片验证准备

## 输入与权重

复用真实产品 API 基准入口 `apps/video-clipper/backend/app/benchmark.py`；它逐个新启后端和 worker，通过会话 API 上传、运行、轮询并在会话清理前归档 `result.json` 与 `output.mp4`。输入清单为 `apps/video-clipper/reports/performance-baseline/inputs.json` 中已通过预检的 `A-short`、`C-short`、`D-short`。视频 SHA 分别为 `e2ea56c398507cc0c1679088121f26ac5a0d6b23ad12502151fb855b13966ef2`、`f270602edffd9c6b081cb0463de9aa97f6d1ef3027b0b16d86ab46941bb07f5c`、`360e3de1018a9656770ea432c903afba44cff29c0052f03ea65606a5200867fd`。

现有模型缓存可用：`apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models` 同时包含 `ball_track.pt`、`yolo11n.pt`、`pose_kpRCNN.pth`；A 只需 ball_track，C 需 ball_track 与 YOLO，D 还需姿态权重。基准入口会按场景复制并校验权重，不需联网下载。尚未执行权重 SHA 校验或模型运行。

## 顺序与耗时

八次串行顺序固定为 A/C/D 全关、A/C/D 新默认、C 动态开、D 动态开。沿性能基线同一三短片的完整产品耗时估算，全关与默认两轮分别约 8分40秒；额外 C/D 动态两次约 7分52秒，合计基线估算约 25分13秒。上传、权重复制、服务启动和机器负载会增加时间；建议预留约 30 分钟。基线单次耗时：A 48.05 秒、C 137.17 秒、D 335.08 秒。此估算不是动态配置的性能结论。

使用唯一全新输出目录，逐次保存 `result.json`、最终 `output.mp4`、请求配置和结果摘要；不覆盖既有基线或历史实验。每次应核对请求中的四个布尔值、worker `result.json` 记录的实际 optimizations 与识别有效参数、原始 predictions、`padding_ms=500`、导出区间和可播放成片。性能阶段时间单列比较；确认区间及成片后再报告速度变化。此为每个视频仅一次运行，不能据此声称稳定性。

## 运行与验收

`inputs.json` 固定八例次序和输入 SHA。新默认例故意省略 `optimizations`，让产品端默认值生效；全关例显式传四个 false；C/D 动态例显式传四个 true。`run.py` 只组装参数并调用现有 `app.benchmark.main`，没有复制产品处理流程。模型目录是现存缓存；基准入口会按场景复制权重并核对 SHA，不会下载。

就绪后从仓库根目录运行 `.venv/bin/python docs/ai/advanced-options/run.py`。脚本使用独立的运行目录 `.runtime/advanced-options/20261023-native` 和报告路径 `reports/advanced-options/results-native.json`；这些路径必须不存在才能启动。

每例检查 `evidence/request.json` 中实际送入 API 的配置，以及 `evidence/result.json` 中 `optimizations`、`recognition.optimizations`、识别参数、`predictions`、`export_ranges` 和 `padding_ms=500`。确认请求和识别参数吻合后，比较原始区间及 `output.mp4`；通过后再单列准备、识别、成片、总耗时和处理速度。基准入口保留每例成片和 JSON 证据。每个视频每种配置只运行一次，不能据此估计稳定性。

轨迹覆盖功能集成后，另有一例 `show-paths-inputs.json` / `run-show-paths.py`：A-short 使用产品默认优化，省略 `optimizations`，并设置 `show_shot_paths=true`。它使用独立输出目录与报告，额外复制并校验 `yolo11n.pt`，不覆盖前八例。
