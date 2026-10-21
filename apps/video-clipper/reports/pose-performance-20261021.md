# 个人视角 Pose 性能对照（2026-10-21）

同一段 **150.9890625 秒 D1** 录像，单次全流程配对：CPU Pose → CUDA Pose，均为 batch 1。识别加导出耗时从 **1425.47 秒降至 470.18 秒，约 3.03 倍**；7 段回合边界和最终 MP4 的 SHA256 完全相同。D1 是已有诊断素材，本次结果不代表独立准确率验收或其他录像的稳定加速倍数。

## 计时范围

两次均使用新进程、同一源文件与缓存权重、`personal` 场景、均衡质量、前后各 500 ms 补时。CPU 基线为冻结且干净的 `f460178` 源码，使用被动计时包装；CUDA 为同一 HEAD 上的未提交优化源码，7 个核心文件在运行起止的 SHA256 一致。**两次驱动不同**：基线在计时前已导入 Torch 等模块，因此 preparation 和总流水线时间不用于直接计算加速比。没有重复采样或置信区间。

| 墙钟阶段（秒） | CPU Pose b1 | CUDA Pose b1 |
| --- | ---: | ---: |
| 识别 | 1385.834543 | 434.822526 |
| 导出 | 39.639142 | 35.360373 |
| **识别 + 导出** | **1425.473685** | **470.182899** |
| Pose 调用累计（嵌套于识别） | 1001.566817 | 73.200338 |
| 准备（驱动不同） | 8.275681 | 3.380087 |
| 流水线（驱动不同） | 1433.749366 | 473.563259 |
| 额外完整解码及参考校验 | 不在基线流水线计时内 | 27.389106 |

Pose 调用累计约快 **13.68 倍**。CUDA 驱动含额外校验的总墙钟为 500.959491 秒；该数字不与基线总墙钟混作加速比。CPU 基线仅 Pose 在 CPU，TrackNet / YOLO 仍使用 CUDA。

## 当前热点与显存

CUDA 运行中，TrackNet 为 162.380897 秒，其中预处理 89.384197、推理及取回 65.238389、点解码 5.716263 秒；Farneback 身体运动计算 129.084363 秒，人物跟踪 6.418597 秒。这些计时存在包含关系，解码生产者还与消费者重叠，不能把所有字段重复相加。

CUDA 运行的 PyTorch 峰值 allocated 为 426849792 bytes（约 407.08 MiB），reserved 为 668991488 bytes（638 MiB）。这是独占基准进程的 PyTorch 计数，未覆盖 CUDA 上下文及整卡所有分配。CPU 基线也有相同的 allocated 峰值，由仍在 GPU 上运行的模型主导，因此不声称节省显存。

## 结果与已知缺陷

- 原始 7 段与补时后 7 段均逐项同序相等，最大边界差为 0 ms；参考身份核验通过，参考文件未修改。
- 两份成片 SHA256 均为 `88b2a65f68ef4a8b7562566f3fbd0d5013f81c90f830f615d2aabe2a30c1c2d4`；均完整解码通过，1977 个视频帧、3092 个音频帧（3166208 个采样），1920×1080、H.264 / AAC，视频时长 65.9558125 秒。
- 检查了源视频及成片的视频损坏帧标志、选段帧数、轨道、时长、音频完整解码及单调 PTS。**没有验证音画同步或与原音轨的波形对应关系**。
- `arm/high/lk_valid/lkarm/lkhigh/speed` 六个信号字段有数值变化，最终区间相同；不声称中间张量全部等价。
- 原有人标诊断指标保持不变：7 个真值均匹配；起点可接受 3/7、终点 5/7、两端均可接受 2/7（允许向外 1500 ms）。第一段原始起点晚 3433.3125 ms，补时导出后仍漏约 2933.3125 ms，性能优化没有修复这一问题。

## batch 2 的限制

仅对 4 个锚点的 8 张真实人物裁剪比较了 CPU b1、CUDA b1、CUDA b2，未运行 batch 2 全片。CUDA b1 与 b2 的选中关节最大坐标差约 **63.90 px**；索引 6（从 0 计数）的裁剪的左踝分数从 3.006475 降至 2.989765，跨过阈值 3，导致 ready 判定改变。默认保持 **batch 1**，batch 2 为实验选项。

探针的 CUDA b1 / b2 推理及取回累计分别为 3.330831 / 0.388525 秒，但变体按顺序执行，第一次 CUDA 调用包含冷启动预热，不能据此认定 batch 2 的稳定吞吐收益。CPU b1 与 CUDA b1 的选中关节最大坐标差约 2.39 px。

## 环境、代码与证据

硬件为 Windows x64、12th Gen Intel Core i7-12700F（WMI 核实，12 核 20 线程）、RTX 3060 Ti 8 GiB；Python 3.11.0、Torch 2.8.0+cu126、Torchvision 0.23.0+cu126、CUDA runtime 12.6、NumPy 1.26.4、OpenCV 4.11.0.86、PyAV 14.2.0、FFmpeg 7.1。识别后 Torch intraop 为 4、interop 为 12，OpenCV 为 1；OPENBLAS / OMP / MKL 环境线程数为 1。

[机器可读摘要](pose-performance-20261021.json)记录输入与三份模型的 SHA256、7 个核心源码的完整 SHA256、驱动 SHA256、版本及关键数值。模型固定来源见[模型注册表](../../../modules/models/assets.py)。输入 SHA256 为 `897858a17a3f8380f6baff726e6eff77fe0e891a49b4fa9fc6176f1e97de722b`，40052580 bytes。

原始证据保存在本机 `ouputs/performance-20261021/` 的 `baseline-D1/performance.json`、`cuda-b1-D1/performance.json`、`comparison.json` 和 `pose-probe/summary.json`。基线驱动为本地 `.runtime/run_baseline.py`；CUDA 驱动为 `scripts/benchmark_clipper.py`。摘要保留实测时的驱动 SHA，后续脚本校验改动不属于该快照。

最终整理工作树以 `SMASH_SUITE_PYTHON` 显式选择原工作区 `.venv-clip` 解释器，运行官方命令 `npx --yes pnpm@9.15.9 run test:backend`：**122 项通过，14.56 秒，1 条 Starlette AnyIO 弃用警告**。原工作区的 88 项 Rally / 后端测试另行通过，耗时 10.63 秒。撰写本报告没有重跑模型或测试。当前交付为 Windows 源码运行，未提供 EXE / 安装包；macOS 本轮未复测。

## 实际 HTTP 应用流程

原工作区通过真实 HTTP 应用 worker 运行同一 D1，确认默认 **CUDA、batch 1**。产品计时 476.985 秒：准备 1.141、识别 439.625、导出 36.219 秒；外部含导入和 HTTP 的计时为 478.630705 秒。`app-default-D1/verification.json` 的全部检查通过：源文件与 8 个执行核心文件在运行期间未变、7 段原始及导出边界与基准相同、成片 SHA256 相同、自动保存文件存在，最终状态为 `completed`。

原工作区保留额外诊断，`recognize.py` 的 SHA256 与独立基准工作树不同；此产品运行只作为默认设备与完整应用流程证据，不混入上面的 CPU / CUDA 配对倍数。`verification.json` 与 `final-state.json` 的 SHA256 和核心文件清单位置已记录在机器可读摘要中。

## 重现新的同驱动配对

在仓库根目录 PowerShell 执行，将四个占位路径替换为本机绝对路径。模型缓存须已有校验通过的三份权重；两个输出目录须为新目录。逐条串行运行，使用同一输入和缓存：

```powershell
$sourceVideo = 'C:\path\to\D1-clip.mp4'
$modelCache = 'C:\path\to\cached-models'
$cpuOutput = 'C:\path\to\new-cpu-b1-output'
$cudaOutput = 'C:\path\to\new-cuda-b1-output'
node scripts/python.mjs scripts/benchmark_clipper.py --source $sourceVideo --scene personal --models $modelCache --output $cpuOutput --pose-device cpu --pose-batch-size 1
node scripts/python.mjs scripts/benchmark_clipper.py --source $sourceVideo --scene personal --models $modelCache --output $cudaOutput --reference (Join-Path $cpuOutput 'result.json') --pose-device cuda --pose-batch-size 1
```

这会生成一组新的当前源码对照，不能冒充本报告历史基线的计时驱动。核对两份 `performance.json` 的源 SHA、核心源码 SHA、设备、计时范围和参考区间差异；`status: passed` 本身不代表识别区间与参考一致。

应用个人视角默认在 CUDA 可用时使用 CUDA，否则使用 CPU；独立 `PoseEstimator()` 仍默认 CPU。需固定 CPU 时，在后端启动窗口设置并重启：

```powershell
$env:SMASH_SUITE_POSE_DEVICE = 'cpu'
$env:SMASH_SUITE_POSE_BATCH_SIZE = '1'
```

移除上述环境变量并重启可恢复自动设备与默认 batch 1；完整安装和恢复命令见 [Windows 说明](../windows.md)。
