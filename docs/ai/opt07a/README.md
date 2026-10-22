# OPT-07A 执行入口

本轮只保留原地归一化。合并颜色与类型转换虽严格等价，但真实单帧 CPU 小样更慢，因此不采用。授权与轮次见 [task.md](task.md)，正式结论见[应用报告](../../../apps/video-clipper/reports/opt07a/README.md)。

## 工作目录与输入

所有命令在 `/Users/bytedance/.codex/worktrees/opt07a-tracknet/smash-suite` 执行；分支 `codex/opt07a-tracknet`，基于 develop `94a8465`。主目录只登记认领，原有用户修改保留。复用同版本 `.venv`，不是依赖重新安装。

- 输入清单：`/Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/reports/performance-first-round/inputs.json`。
- 模型缓存：`/Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models`；逐一校验 ASSETS，不下载。
- 原版 predictor：`apps/video-clipper/.runtime/opt07a/reference/predictor.py`，字节与起点提交相同，SHA 见 task.md。丢失时应从该提交恢复，不能拿候选当原版。
- 当前 OpenCV 5.0.0 保持生产 `setNumThreads(1)` 调用，其后实际记录为18，不能称单线程；torch为4。本轮两版环境一致，旧基线秒数不作为归因对照。

## 真实帧严格检查

下面是主控实际使用的入口，输出目录必须尚不存在。`probe-controller` 保留最初合并转换候选的证据；`probe-retained` 核对最终生产实现。

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python docs/ai/opt07a/probe.py \
  --inputs /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/reports/performance-first-round/inputs.json \
  --models /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models \
  --reference-source apps/video-clipper/.runtime/opt07a/reference/predictor.py \
  --output apps/video-clipper/.runtime/opt07a/probe-retained
```

完整解码A/C/D到EOF，仅保存选定真实帧。原版、仅原地、合并转换、实际保留版的真实batch/热图及严格比较保存为 `report.json` 和 `model-io.pt`。前后线程、代码来源、媒体与权重SHA均保存；不把合成回归当模型验收。

## A/C 识别对照

入口是 `docs/ai/opt07a/recognition.py`，参数复用上方 `--inputs`、`--models`、`--reference-source`，另传 `--variant baseline|candidate`、`--case A-short|C-short`、`--output 新目录`。四次分别使用 `apps/video-clipper/.runtime/opt07a/recognition/{baseline,candidate}/{A-short,C-short}`，串行、独立新进程；不渲染成片。

每次保存 `run.json`、完整 `result.json`、`statistics.json` 与 `resources.json`。核对回合、推导导出范围、选人诊断与工作量计数；预处理是识别分项，不与父项相加，RSS与MPS分开记录。

## 当前证据与剩余检查

- 主控最终真实帧严格检查：已通过，12组、31张独立图像；缓存未串图、释放后为0。
- A/C四次识别：已完成；完整区间、推导导出范围、诊断及工作量一致。
- 单帧交错顺序小样与操作级分配：已执行，原始 `preprocess-small.json` 保留；不是进程峰值或稳定速度证明。
- 开发聚焦回归：4 passed。统一查看器已检查实际播放、首段前后定位和切换；后端全量与独立验收的执行结果见任务状态及验收方记录。
- 前端、导出、D完整姿态和长片未执行，不在本项已确认验证范围。

## 保存结果查看器

```sh
.venv/bin/python -u .agents/skills/review-video-results/scripts/review.py \
  --data modules/models/tracknet/.runtime/opt07a-review.json --port 0
```

主控本次网址为 http://127.0.0.1:64357/，两条算法行均来自保存的原始识别结果；A媒体偏移91ms，C为0ms，来自实际probe，不猜帧率。当前查看器进程和标签页保留，A/C实际播放与切换已检查；截图在所属应用报告。

## 集成后的复查入口

2026-10-22已按用户确认合入develop。以上路径记录原任务执行位置；后续复查从主目录 `/Users/bytedance/workspace/experiments/smash-suite` 执行相同相对命令。原始证据已复制到主目录同名 `.runtime/opt07a/`，查看器数据保留到主目录 `modules/models/tracknet/.runtime/opt07a-review.json`。证据复制逐文件SHA清单见 `evidence-preservation.json`；集成检查记录见 `verifier/integration-output.md`。
