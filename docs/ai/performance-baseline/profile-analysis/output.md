# 原生剖析汇总脚本准备结果

已准备 `native_profiles.py`，供控制器确认 A/C/D 的 `native.trace` 完整保存后，依次导出 TOC、Time Profile、Metal GPU intervals 和 OS Signpost，再按 `recording.json` 中的目标 PID 汇总。脚本要求显式传入控制器完成确认标志；每条导出命令保存完整命令、退出码和日志，失败保留产物并返回非零状态。若目标 CPU、GPU Active interval 或目标进程 signpost 数据为空，或无法解析必需字段/引用，汇总失败，不把全系统数据冒充目标数据。

剖析预检 XML 仅按授权读取每个文件前 16,000 字节，未导出或全量解析正式 trace。可见 schema 与实际 row 证据包括：

- `time-profile` 的字段为 Sample Time、Thread、Process、Core、State、Weight、Backtrace；嵌套 Process/PID、frame/binary 和重复字段通过 XML `id`/`ref` 索引解析。样本显示 Weight 原始值 1,000,000 对应格式值 1.00 ms，Sample Time 原始值以纳秒表示。Backtrace 首列为采样叶函数；inclusive symbol 每个样本内去重。
- `metal-gpu-intervals` 的开始字段 schema 名为 `Creation`、engineering type 为 `start-time`；两列都叫 engineering type `duration`，但 schema 名分别为 Duration 和 CPU to GPU Latency。脚本依据 schema 列顺序区分，只对目标 PID 的 Active 区间做全局并集，不把嵌套或跨队列时间直接相加。
- `os-signpost` 的字段包括 Timestamp、Process、Event Type、Signpost identifier、Name、Format String、Subsystem、Category、Message 等；已见 Begin/End 及嵌套消息字段。预检样本中 `text-backtrace` 列由 `sentinel` 表示空值，脚本按该已观察到的实际形式处理。PyTorchMPS 按精确 subsystem 值单列事件、名称、格式/消息和配对区间，并输出实际字段样本及区间并集。

汇总会保留 CPU 样本数、时间范围、估算 CPU weight 秒、叶符号/二进制 exclusive top 50、递归符号去重后的 inclusive top 50、全叶二进制权重和原生函数示例；GPU 状态计数、范围、Active 并集；目标进程 Signpost 事件和 PyTorchMPS 子集。CPU weight 只表示采样估算，跨线程可大于墙钟；inclusive 权重不可相加；函数名包含 torch 不等于 Python 执行。若报告 GPU 时间占比，其分母必须是本次 trace 观测范围，不能称正式 GPU 利用率。

`artifact-index.json` 实现对原始 trace bundle 每个文件、原始 py-spy SVG、导出的 XML/TOC/日志做 SHA-256 和大小记录；目录摘要由相对 POSIX 路径与内容 SHA-256 按名称排序后规范计算。原 trace 保持原位，不复制。

验证仅运行 Python 语法编译，结果通过。没有执行脚本、`xctrace export`、正式 XML 解析、trace/SVG 哈希、测试、解码或模型推理；正式 trace 与剖析导出尚未在本轮开始。

## 识别窗口与时钟映射准备

按新增契约，脚本现在从每个 `profile-control-<case>/evidence/benchmark-clock.json` 读取 `benchmark_start` 与 `rendering` 单调时钟值，从 `recording.json` 读取 `monotonic_to_epoch_offset_s`，将两个端点映射到 epoch，再减去 TOC 的 `run/info/summary/start-date` 得到 trace-relative 识别窗口。TOC start-date 的容差按毫秒精度记录；缺少字段、时区、非正/不可解析时长或窗口超出 trace duration 时会明确失败，并要求核对 trace 时钟原点，不做自动猜测。

CPU 与 GPU 的主要汇总字段现在取识别窗口，`full_trace` 保存对应全范围统计，`outside_recognition_window` 单列窗口外目标统计；GPU Active 区间先裁剪到窗口再求并集。OS Signpost 保留目标 PID 全范围汇总，并额外统计窗口内 PyTorchMPS 事件类型与数量。脚本还将 CPU 样本、GPU interval、Signpost 时间范围与 TOC duration 比较，输出 trace 时钟原点校验结果；不在 duration 范围内会失败。原始 XML 和 py-spy SVG 均不改动。新增实现位于 `native_profiles.py` 的 `parse_epoch`、`parse_duration_seconds`、`recognition_window` 与三类分析函数中。

本轮仅对脚本做 Python `compile()` 语法编译，结果通过；首次调用 `python` 不存在，随后使用 `python3` 成功。没有运行脚本、xctrace export、正式 XML 解析、trace/SVG 哈希、测试、解码或模型推理。trace 数据时间范围与映射窗口的实际一致性仍待控制器确认三份录制全部保存后执行分析时验证。

## A 原生补录路径契约

脚本现在从各自 `recording.json` 的 `native_benchmark_clock_path` 读取识别窗口时钟，从 `native_case_directory` 保存原生样本归属；不再假定 A 的 clock 在旧 `profile-A/A-short` 或固定 evidence 目录。目标进程仍使用本次原生录制的 `target_pid`。py-spy SVG 改为读取 `recording.json.python_capture.flamegraph` 指向的原始文件，并在产物元数据中保留整个 `python_capture` 对象；因此可表达 A 原生补录 PID 与此前 Python 捕获 PID 不同，不能声称两者同进程或同次捕获。

本次只对更新后的 `native_profiles.py` 再次做 Python `compile()` 语法编译，结果通过；未运行导出、XML 分析、trace/SVG 哈希或模型任务。

## A 原生补录分析结果

按主控最新授权，仅分析 A。首次四项 xctrace 导出均成功，但分析遇到 `sample_time` 先使用后赋值的脚本错误；失败的 `full-native-A/summary.json`、TOC、三份 XML、命令日志与 trace/SVG 文件索引均保留。修复后复用这组既有 XML 做解析，没有重复导出或复制大文件。中断的重导出尝试 `full-native-A-r1` 未用于分析；成功结果单独写在 `full-native-A-parse1/`。

成功摘要为 `apps/video-clipper/.runtime/performance-baseline/profile-analysis/A/full-native-A-parse1/summary.json`，有效文件索引为同目录 `artifact-index.json`。摘要状态为 `passed`，无错误；时间窗口 `[1.504132, 39.659329]` 秒（trace-relative，约 38.155 秒）落在 49.105 秒 trace 内。Time Profile、Metal intervals、Signpost 的目标数据范围均通过 TOC duration 原点校验，三表均无 unresolved refs 或 duplicate IDs。

- CPU：56,491 行均属于原生目标 PID 42,952；窗口内 56,257 个 Running 正权重样本，估算累计 CPU weight 为 56.257 秒（跨线程累计，不等于墙钟）。窗口 leaf top 是 `cpu_upsample_generic_aa<float, true>` 相关 TensorIterator 路径，15.553 秒估算 weight；其次包括地址未符号化的 `0x1157223dc`（5.497 秒）、PyTorch copy kernel（4.279 秒）和 vectorized divide kernel（3.610 秒）。
- GPU：94,496 行中 93,928 行属于目标 PID，均为 Active；窗口裁剪后的全局并集为 21.873 秒、10,081 个合并区间。这是 trace 区间覆盖时长，不代表 GPU 利用率。
- Signpost：375,772 行中 355,624 行属于目标 PID；其中 PyTorchMPS 有效事件 170,595 个（Event 56,867、Begin 56,861、End 56,867），匹配区间 56,861 个、未匹配 6 个，嵌套区间并集为 15.897 秒。窗口内事件数同为 170,595。

原生 A 目标 PID 为 42,952；关联的既有 py-spy 捕获 PID 为 38,406，来自相同冻结源码/输入但属于独立捕获并含附加等待，不是同一进程或同一轮剖析。重试 artifact index 为 7,169 字节，引用首次 trace 文件树清单与 XML hashes，没有再次遍历 500 文件 trace bundle。未启动 C/D、模型或采样器。

## CNN 短窗口探针核验与 C/D 窗口解析准备

仅核对已有 `cnn-window-probe/` 证据并解析现成的三份 XML，未启动采样、真实模型或新导出。`ready.json` 与 `execution.json` PID 均为 44,500、UID 为 501；探针和 trace 返回码均为 0，日志记录 `Recording completed` 与 `Output file saved as cnn.trace`。TOC 记录 trace 长 7.890 秒（请求时限 5 秒），已有探针报告 449 次迭代、12.002 秒。按实际 XML `id/ref` 解析后：CPU 4,253 行/4,253 正权重样本，目标 GPU 2,365 行且 2,365 个 Active interval，目标 Signpost 56,821 行、PyTorchMPS 28,224 个事件。三表均无 unresolved refs 或 duplicate IDs，导出日志全部成功，核验状态 `passed`。小型结果保存在 `.runtime/performance-baseline/cnn-window-probe/verified.json`。

`native_profiles.py` 已准备 `--windows` 分支供未来 C/D 使用：按 `recording.json.native_windows` 对每个 `observation`/`pose` trace 独立导出、解析和建索引；分析窗口取 TOC 实际 trace 覆盖与 `benchmark_start` 至 `rendering` 的交集，并保留 trace 覆盖、完整映射端点、stage 时钟点和所属 stage。阶段核对只读取 recording 明确给出的 `stage_events_path` 与 `stage_current_path`，仅使用事件字段 `monotonic_s/status/stage/progress`；以 trace 起点 epoch 减 recording offset 映射到 monotonic，对分析窗口内阶段边界或阶段不匹配明确报错，不用预测值掩盖。Observation 要求目标 CPU、GPU Active、MPS 均非空；Pose 要求 CPU 非空，GPU/MPS 同时为空时标记为可能的 CPU 模型路径，仍以阶段事件为准。每窗口单独输出和复用，不复制 XML/trace；复用时一次只处理一个 case，并传该 case 的先前 run 目录。

本轮脚本只做 Python `compile()` 语法检查并通过。未运行 `--windows`，C/D trace 尚未开始或解析；阶段路径与字段会在未来由控制器 recording.json 提供，实际时间线正确性仍待真实数据核对。

## C/D 阶段窗口实际分析（2026-10-21）

按主控授权运行 `--controller-confirmed-complete --windows --cases C D --run-id phase-windows-v1`。普通 sandbox 首次阻止在 worktree 的应用 `.runtime` 创建结果目录，未开始解析；使用已授权的同一命令提升权限后完成四项 XML 导出（C observation、D observation/pose 各含 TOC 与三表）。首次分析保留在 `profile-analysis/{C,D}/phase-windows-v1/`，未覆盖。四份导出退出码均为 0，随后修复脚本中的 `ref_problems` 遍历：`analysis` 字典还含整数 `target_pid`，旧代码对其按子字典读取导致 `TypeError: 'int' object is not subscriptable`。另修复 `--windows --reuse-from` 参数预检，使其按 case run 目录内各窗口检查现存 export/index。语法编译与 `git diff --check` 通过。

修复后只复用首次已成功导出的 XML，未重导出或重读/哈希大型 trace；新摘要和小型索引位于 `apps/video-clipper/.runtime/performance-baseline/profile-analysis/{C,D}/phase-windows-v1-retry1/`。C observation 与 D observation 仍正确标记 `failed`：目标 PID 的 OS Signpost 最大时间分别为 13.605134833 秒和 9.739336875 秒，TOC duration 分别为 13.045600 秒和 9.189937 秒。越界事件都是 subsystem `PyTorchMPS`、name `PyTorchOperationIntervals` 的 `End`，超过 trace duration 约 0.560 秒与 0.549 秒。该误差保留为原点校验失败；未加宽容差、未隐藏异常。D pose 摘要为 `passed`。三个分析窗口分别与其所选阶段一致，阶段边界未跨越。

| 窗口 | trace 秒 / 分析窗 | CPU 目标行；窗口 Running 样本 / 累计 weight 秒 | GPU 目标行；窗口 Active 并集秒 | Signpost 目标行；窗口 MPS 事件 | 状态 |
|---|---|---:|---:|---:|---|
| C observation | 13.045600 / [0, 13.045600] | 16,515；16,515 / 16.515 | 34,787；7.438076 | 146,149；66,532 | failed：MPS End 越界 |
| D observation | 9.189937 / [0, 9.189937] | 10,746；10,746 / 10.746 | 17,948；3.032870 | 105,769；50,069 | failed：MPS End 越界 |
| D pose | 8.956340 / [0, 8.956340] | 11,246；11,246 / 11.246 | 0；0 | 1,363；0 | passed；CPU 有效，目标 GPU/MPS 均为空 |

三窗口的 XML unresolved refs 和 duplicate IDs 均为零。CPU weight 是跨线程累计采样估计值，不是墙钟；GPU Active 为裁剪窗口后全局区间并集，不是利用率。Observation CPU 叶热点前三：C 为 torch CPU `cpu_upsample_generic_aa` 4.912 秒、torch copy kernel 1.336 秒、torch vectorized divide 1.144 秒；D 为 torch TensorIterator callback 2.168 秒、OpenCV `FarnebackOpticalFlowImpl::calc` 1.772 秒、`FarnebackUpdateMatrices` 0.693 秒。Pose 热点为 torch `unfolded2d_copy` 1.019 秒、地址符号 `0x18a4dd2fc` 0.964 秒、torch kernel wrapper 0.908 秒。CPU热点按叶符号 exclusive weight 排序。

首次运行已生成 `phase-windows-v1` 的 XML、日志、失败摘要和索引；修复后索引位于 `phase-windows-v1-retry1`，通过原窗口 artifact-index 引用原 trace 与导出物。C/D observation 原点失败是当前唯一未解除的状态问题；没有改变证据或将失败项标为通过。没有运行模型、采样器或测试。

### Observation Signpost 越界事件专项核对

依最新授权只读重解析既有 `phase-windows-v1` observation `os-signpost.xml`，目标 PID 仍按 XML Process/PID 引用解析。按时间排序，以精确 `(signpost identifier, subsystem, category, name)` 分组，End 匹配该组最近未配对 Begin（LIFO）；未调整偏移或容差。完整逐事件清单见 [`signpost-boundary-events.json`](../../../../apps/video-clipper/.runtime/performance-baseline/profile-analysis/signpost-boundary-events.json)，包含所有超出 TOC 末端的目标事件和每个 End 的配对时间、Begin 是否在 TOC 内及 End 是否晚于 Begin。

结果不满足恢复授权的边界分类条件，因此 C/D observation 仍为 `failed`，没有生成 `phase-windows-parse2` 或将失败改标通过：

- C 的 TOC 时长为 13.045600 秒，目标进程有 8,569 个超界事件；D 为 9.189937 秒，有 4,755 个。两者超界事件均不止 PyTorchMPS interval End：包含 PyTorchMPS Begin/Event，也包含 `com.apple.metalperformanceshadersgraph` 的 MPSGraph Begin/End。
- C 有 3,395 个超界 End，均配对且 End 晚于 Begin；其中仅 7 个 Begin 在 TOC 内，其余 Begin 已在 TOC 结束之后。D 有 1,873 个超界 End，均配对且 End 晚于 Begin，但 Begin 全部在 TOC 外。故既不是“所有超界事件仅 PyTorchMPS interval End”，也不是“每个 End 的 Begin 都在 TOC 内”。
- 超界 event-type/subsystem/name 计数：C 为 PyTorchMPS `PyTorchOperationEvents` Event 1,707、`PyTorchOperationIntervals` Begin 1,704 / End 1,707、`PyTorchCopyEvents` Event 74、`PyTorchCopyIntervals` Begin/End 各 74；另有 MPSGraph Encode Begin 1,605 / End 1,604 和少量 MPSGraph 编译/初始化 Begin/End。D 为 PyTorchMPS `PyTorchOperationIntervals` Begin 959 / End 952、`PyTorchOperationEvents` Event 952、`PyTorchCopyIntervals` Begin/End 各 49、`PyTorchCopyEvents` Event 49；另有 MPSGraph Encode Begin 873 / End 872。
- C 最早十个超界 End 的 ID 为 506744、506750、506756、506769、506775、506781、506794、506800、506802、506804；对应 Begin 时间分别为 13.044121583、13.044163583、13.044251333、13.044316、13.044354583、13.044430750、13.044538500、13.049589791、13.049594291、13.056757458 秒。前七个 Begin 在 TOC 内，后三个在外。
- D 最早十个超界 End 的 ID 为 243204、243207、243213、243219、243232、243238、243244、243257、243262、243268；对应 Begin 时间分别为 9.293272083、9.293915875、9.294003708、9.294082625、9.294168083、9.294198375、9.294236125、9.294291375、9.294335708、9.294370500 秒，均在 TOC 外。

边界清单核对的窗口是 `[0, TOC duration]`，与当前分析窗口完全相同。窗口内 PyTorchMPS 数量仍与原 retry1 摘要一致：C 66,532，D 50,069；TOC 外事件没有被计入窗口。CPU/GPU 目标原始范围仍在 TOC 内：C CPU `[0.247288166, 13.044105166]`、GPU `[0.248266208, 13.044904375]` 秒；D CPU `[0.249635083, 9.189936750]`、GPU `[0.247882500, 9.126031250]` 秒。两窗口仍匹配各自 observation 阶段，三表 unresolved refs 与 duplicate IDs 均为零。官方 PyTorch v2.8.0 `MPSProfiler.mm` 的 completed-handler 语义可支持 End 可能晚于 enqueue/Begin 的解释，但本数据的超界 Begin/Event 及 MPSGraph 事件表明，不能将全部越界事件归类为该情形；也没有证据证明具体是 Instruments 缓冲/导出造成。该根因保持未确认。

### 按就绪标记复用解析为约 8 秒主窗口

按新增授权，以已存在 XML/trace 索引生成 `phase-windows-parse2/`，无重导出或原始大 trace 哈希。主窗口从 `max(TOC start, benchmark_start, ready_monotonic_s + offset)` 到 `min(TOC end, rendering)`；TOC 完整时段、就绪点映射和就绪前数据都保留。`ready_monotonic_s` 是 0.1 秒轮询观察值，真实转换可能提前至多一个轮询周期；确定性主窗口从观察值开始，不对该边界人为回移。就绪前段是完整 TOC 中未纳入主统计的前缀。

| 窗口 | ready 相对 TOC 秒 | 完整 TOC 秒 | 主窗口跨度 | CPU 主窗 Running 样本 / weight 秒；就绪前样本 / weight 秒 | GPU 主窗 interval 行 / Active 并集秒；就绪前行 / 并集秒 | MPS 主窗 / 全部 / 就绪前 | 状态 |
|---|---:|---:|---:|---:|---:|---:|---|
| C observation | 5.095073 | 13.045600 | 7.950527 s | 10,411 / 10.411；6,104 / 6.104 | 22,039 / 4.634414；12,748 / 2.803662 | 65,855 / 71,872 / 677 | failed：完整 TOC 有非单一类型边界事件 |
| D observation | 1.245430 | 9.189937 | 7.944507 s | 9,559 / 9.559；1,187 / 1.187 | 16,098 / 2.661880；1,850 / 0.370990 | 49,367 / 53,079 / 702 | failed：完整 TOC 有非单一类型边界事件 |
| D pose | 1.043334 | 8.956340 | 7.913006 s | 10,245 / 10.245；1,001 / 1.001 | 0 / 0；0 / 0 | 0 / 0 / 0 | passed |

就绪前 MPS 数量为完整 TOC 目标 MPS 事件减主窗口数量和 TOC 外 MPS 事件；窗口区间严格裁剪到就绪点至 TOC/渲染结束交集。完整 TOC 与主窗口的阶段证据各自保留，三窗两者均只观察到目标选定阶段且无跨界。全表 unresolved refs、duplicate IDs 仍为零；C/D observation 的 CPU 与 GPU 原始目标时间范围在 TOC 内，失败仍仅由 Signpost 全范围越界校验触发。边界事件的专项配对条件仍不成立，不把源码中的异步 End 语义推广为所有边界事件的证明。D pose 的 GPU/MPS 目标为空；本阶段契约允许该结果。分析脚本当前 `window_mapping` 记录 ready 单调/epoch/trace-relative 值、0.1 秒轮询误差口径、TOC duration、完整 TOC 与主窗；摘要另存完整 TOC 阶段校验。

### 受控探针复现后最终窗口汇总

按最新授权对工具口径作最小调整，并从 `phase-windows-v1` 的 XML/原始索引复用生成 `phase-windows-final/`；没有重导出、重新哈希 trace、重跑模型或采样。已有完整边界事件表被引用；另外在每个 observation 摘要和索引中记录受控探针诊断 `cnn-window-probe/stop-boundary-check.json` 的路径/hash，且核对其 C/D TOC 与 Signpost 终点和当前输入相符。该证据重现约 0.55 秒跨表停止边界差异，但不证明 xctrace 内部缓冲原因。

| 窗口 | 状态 | 主窗 | CPU 样本 / 累计 weight 秒 | GPU interval 行 / Active 并集秒 | MPS 主窗事件 / 配对 interval 并集秒 | 主窗外 CPU 样本、GPU 并集、MPS 事件 |
|---|---|---:|---:|---:|---:|---|
| C observation | `passed_with_signpost_tail` | 7.950527 s `[5.095073, 13.045600]` | 10,411 / 10.411 | 22,039 / 4.634414 | 65,855 / 5.652257 | 前缀 6,104、2.803662 s、677；TOC 外 MPS 5,340 |
| D observation | `passed_with_signpost_tail` | 7.944507 s `[1.245430, 9.189937]` | 9,559 / 9.559 | 16,098 / 2.661880 | 49,367 / 3.538855 | 前缀 1,187、0.370990 s、702；TOC 外 MPS 3,010 |
| D pose | `passed` | 7.913006 s `[1.043334, 8.956340]` | 10,245 / 10.245 | 0 / 0 | 0 / 0 | 前缀 1,001；GPU/MPS 仍无目标数据 |

最终摘要位于 `apps/video-clipper/.runtime/performance-baseline/profile-analysis/{C,D}/phase-windows-final/`，每个窗口含 `summary.json` 与 `artifact-index.json`。摘要的 `trace_time_origin_validation.tables` 保留 Signpost `within_toc_trace_duration=false` 与原始范围/尾长；CPU 和 GPU 的 TOC 原点检查仍严格通过。Signpost 超界事件类型、subsystem/name 计数、完整逐事件/配对索引、受控探针证据和 SHA 均有明确路径。MPS 主窗事件及配对 interval union 仅计 ready 到 TOC 终点的裁剪范围；完整 trace union 与前缀/TOC 尾部各自保留，不把 MPS 区间覆盖时长解释为 GPU 执行时间。三个窗口的分析窗和完整 TOC 阶段都匹配，XML unresolved refs 与 duplicate IDs 均为零。该状态表示所选短窗证据可用于局部瓶颈分析，不代表导出表所有 Signpost 时间都落在 TOC 内；最终结论仍待独立验收复核。


### 冻结前机械修正：phase-windows-final-v2

按授权复用各 case 的 `phase-windows-v1` XML，生成 `apps/video-clipper/.runtime/performance-baseline/profile-analysis/{C,D}/phase-windows-final-v2/`；未重导出、未重跑模型/采样、未重新哈希原始 trace。CPU 原点检查现读取 `time_profile.full_trace.target_sample_time_range_s`，完整 CPU 目标范围分别为 C observation `[0.247288166, 13.044105166]`、D observation `[0.249635083, 9.189936750]`、D pose `[0.241112583, 8.955807791]` 秒，均在对应 TOC 范围内。

边界事件原始清单从本目录迁移至 `apps/video-clipper/.runtime/performance-baseline/profile-analysis/signpost-boundary-events.json`，字节数 5,100,641，SHA-256 `a657d9be1dcb03e150070d1b1f5a0f3582782469458968647ac6318a42d9831e`；`docs/ai/` 中已不保留该原始大文件。当前代码与 final-v2 摘要/索引引用新的绝对路径及相同 SHA。

与 `phase-windows-final` 相比，三窗主窗口数值、阶段核对、错误列表及状态均未改变：C observation 和 D observation 为 `passed_with_signpost_tail`，D pose 为 `passed`。唯一数值字段更新是原始 CPU 全范围起点；窗口 CPU/GPU/MPS 指标不变。Python AST syntax 检查和指定文件 `git diff --check` 通过；`py_compile` 因系统 Python 缓存目录不可写而失败，未创建缓存文件，AST 检查已覆盖语法验证。
