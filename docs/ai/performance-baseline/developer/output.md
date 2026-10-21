# 第一轮开发交付

## 版本与状态

- 基线提交：`979caeb1cefedd78b2cebac52ca38f28a84d7563`；分支 `codex/performance-baseline`，未提交、未推送、未合入。
- 本轮工作树 SHA256：`604b14cfa5ad0d1e2a58f78cf7befcc6674e6abade221269d504880eab64e7b3`。生成算法为 runner 的 `code_version()`：所有受 Git 管理和未忽略文件（排除 `docs/ai/`）分别 SHA256，按路径排序后 JSON 再 SHA256；含本轮源码、测试和协议文档。逐文件清单：`apps/video-clipper/.runtime/performance-baseline/developer/version.json`。
- 实现与合成验证完成，本轮未启动六次正式真实处理、三次真实剖析；未宣称任务验收通过。按派发边界停止开发，等待主控下一次派发。

## 修改

| 文件 | 变化 |
| --- | --- |
| `apps/video-clipper/backend/app/benchmark.py` | 真实产品 HTTP 导入/启动/查询，WebSocket 持续续租；每组新后端/会话/worker，顺序运行。预校验输入及固定模型 SHA，复制模型缓存后再启动，计时内仍执行正常权重校验/加载。保存环境、源码与算法配置；每秒采后端及递归子进程 CPU/RSS、目录/磁盘；关闭会话前归档结果/视频/日志及 SHA；失败保存；生成所属报告 JSON。 |
| `apps/video-clipper/backend/app/sessions.py` | 仅通过内部环境配置向 request 传可选 benchmark 参数，保存明确 worker/阶段单调时钟事件。公开 HTTP、JobState 和正常产品计时契约不变。 |
| `apps/video-clipper/backend/app/worker.py` | 从 worker 向 recognize 传可选统计；剖析模式的明确 ready/release 握手，默认正式模式不等待也不生成 profile-ready；可选 MPS signpost；worker 内 MPS 内存每秒采样；成功/异常保存统计。 |
| `modules/rally/statistics.py` | 最小聚合 collector，主阶段嵌套时暂停父计时，主阶段互斥；子项另存且说明不应相加，无逐帧日志。 |
| `modules/rally/recognize.py` | A/C/D 的模型初始化、观测、人物/轨迹、动作、回合判断、中间写盘边界；复用 FileFrameSource 解码/转换统计，D 第二遍解码与姿态调用计数。 |
| `modules/rally/tracknet_rally.py`、`modules/rally/scenarios/high.py` | A 的逐帧回合判断可选统计，暂停观测父阶段，避免重复计时。 |
| `modules/models/tracknet/predictor.py` | 复用已有 preprocess/inference+transfer/point decode，累计调用、帧与候选峰计数，不改输出。 |
| `pyproject.toml` | 开发 extra `benchmark`：psutil 7.2.2、py-spy 0.4.2；不加入发行依赖。 |
| `apps/video-clipper/backend/tests/test_benchmark.py` | 8项合成/确定性测试，详见下方边界。 |
| `apps/video-clipper/reports/performance-baseline.md`、应用 README | 协议、计时/采样口径、运行与剖析握手入口、已验证与未验证边界；没有虚构真实性能数值。 |

未改算法参数、模型/采样/线程/自动设备选择、质量档、产品请求和前端。原仓库 outputs 未读写；只尝试复制回放清单中的模块缓存，首项不存在即停止，未恢复或改写旧观测。工作树 `.venv/` 是指向既有环境 bin/lib/pyvenv.cfg 的链接目录，原环境未改。

## 验证

- 完整等价后端命令 `.venv/bin/python -m pytest`：**100 passed, 1 warning in 10.81s**。warning 是既有 Starlette/httpx TestClient 弃用提示。
- 日志：`apps/video-clipper/.runtime/performance-baseline/developer/backend-tests.txt`；SHA256 `2ac9bbc7a6de9c7a44b7a227d81019c196837d44264c790f1e429d48962ad6dd`。
- 新增8项：确定时钟下主阶段互斥及失败写盘；A 用实际合成 MP4 解码、确定模型观测检查统计开关输出相同；C/D 用确定观测与判断替身检查新增阶段边界输出相同；递归进程覆盖及目录字节口径；真实 HTTP+WS、独立合成 worker、FFmpeg 成片和归档清理（正式/剖析握手各一组）；worker 异常日志/时钟归档。
- 合成 worker/确定模型观测明确不算真实模型验证，也不替代16例保存观测回放。
- `git diff --check`：通过。
- CLI `PYTHONPATH=apps/video-clipper/backend .venv/bin/python -m app.benchmark --help`、修改 Python 语法检查：通过。
- `pnpm run test:backend`：已执行但被本机 pnpm 12.6 自动安装时的供应链策略挡住：`ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION`，`watchpack@2.6.3` 无法在 registry manifest 检查。未改 lockfile、未放宽策略；上方完整 pytest 正是该 package script 的实际命令。
- 16例 `modules.rally.experiments.replay`：已尝试，因保存观测缺失失败；首个报错为 worktree 的 `modules/rally/.runtime/m1-a-tuning-20261016/A1-01/01-01-clip/flight-diagnostics.jsonl`。随后按清单复制原模块缓存，原目录 C1 首项也不存在。已按最新 input 停止恢复，未改期望；用户替代方案尚待决定。

## 正式运行命令

主控确认媒体索引全部必要预检 `passed` 且准备模型目录后，在本任务 worktree 执行。以下路径均相对 worktree，输出/报告须使用新路径：

```sh
PYTHONPATH=apps/video-clipper/backend .venv/bin/python -m app.benchmark \
  --inputs apps/video-clipper/.runtime/performance-baseline/media/inputs.json \
  --cases A-short A-long C-short C-long D-short D-long \
  --models apps/video-clipper/.runtime/performance-baseline/models \
  --output apps/video-clipper/.runtime/performance-baseline/baseline \
  --report apps/video-clipper/reports/performance-baseline-results.json
```

`result.timings` 逐值复制产品 `state.timings` 和 `state.elapsed_s`，包含 worker 启动、Python imports、权重正常校验加载，不做任何净计时扣除。内部 clock 只是事件证据；导入视频、准备模型缓存和归档不在产品计时内。

## 三短剖析及握手

主控已批准工具探针见 `controller/profiler/verified.json`；本轮实现没有再提权运行工具。每短片独立执行，依次替换 case/output/report 中 A 为 C、D：

```sh
PYTHONPATH=apps/video-clipper/backend .venv/bin/python -m app.benchmark \
  --inputs apps/video-clipper/.runtime/performance-baseline/media/inputs.json \
  --cases A-short \
  --models apps/video-clipper/.runtime/performance-baseline/models \
  --output apps/video-clipper/.runtime/performance-baseline/profile-A \
  --report apps/video-clipper/reports/performance-profile-A.json \
  --profile-wait --profile-timeout 300 --mps-signposts \
  --py-spy-path /private/tmp/smash-performance-tools/bin/py-spy
```

runner 将 worker 的 `profile-ready.json` 明确事件复制到 `profile-A/A-short/profile-ready.json`，内容包含 `pid`、`release_file`、`session_directory`，以及完整 `py_spy_command` 参数数组。主控可直接使用该数组，经已经预检的管理员采样方式运行 py-spy；runner 本身不提权、不启动 root helper。其命令等价于：

```sh
/private/tmp/smash-performance-tools/bin/py-spy record \
  --pid <ready文件的pid> \
  --output <profile-A/A-short的绝对路径>/python.speedscope.json \
  --format speedscope --rate 100
```

另一采样终端使用同一实际 PID：

```sh
xcrun xctrace record --template 'Metal System Trace' \
  --instrument 'Time Profiler' --instrument os_signpost \
  --attach <ready文件的pid> \
  --output <profile-A/A-short的绝对路径>/metal.trace --no-prompt
```

以上占位值须从明确 ready JSON 读取，不能用进度文字或“子进程已启动”代替确认。主控确认 py-spy 与 xctrace 已实际附加、录制开始后，用 Python 读取 JSON 内 release_file 创建空文件：

```sh
.venv/bin/python - <<'PY'
import json
from pathlib import Path
ready = json.loads(Path('apps/video-clipper/.runtime/performance-baseline/profile-A/A-short/profile-ready.json').read_text())
Path(ready['release_file']).touch()
PY
```

此后 worker 继续正常权重校验、模型初始化、识别与导出。超过300秒未释放则按失败归档。剖析含等待与采样开销，报告 kind 为 profile，不作正式基线。worker 退出后主控停止/确认采样器完成；trace、导出表和采样结果应留在该 `.runtime` 目录并另存 SHA 与目标 PID 有效样本证据。当前 runner 不自动判断采样器是否有效，也不会把它算成通过。

## 未验证与下一轮入口

1. 六份真实输入尚未由本开发角色处理；runner 本轮只验证合成编排及统计等价，真实模型/设备、真实成片与性能数值均未验证。
2. 三份真实工具剖析、trace 导出、目标 PID 样本有效性与热点分析尚未执行。工具数秒预检为主控证据，不等于三片正式剖析完成。
3. 16例回放数据缺失仍阻塞既定验收；不擅自改为合成或三短对照。待用户确认和主控新 input。
4. 每秒采样可能遗漏短命进程/瞬时峰值，报告只称观测峰值；RSS 与 MPS allocated/driver 不相加。主阶段间公共校验/调用间隔没有硬分摊为某个阶段。
5. 本轮未运行前端类型检查（公开契约与前端无改动），未打包、提交、推送或合入。路线图与认领由主控按任务状态维护。

主控下一步可冻结此实现后派发真实运行；如实现发生变化，版本清单和受影响验证必须重新生成。真实报告与图表须基于随后保存的实际数据，不能使用当前合成测试估算收益。

# 第一轮补充交付：用户后续确认

本节覆盖上文旧验收要求、旧运行命令和旧版本状态；上文保留为首次交付历史。用户已批准用三份真实短片的统计开关对照替代缺失35份缓存的16例历史回放，旧检查不再是当前验收阻塞，也没有被记为通过。仍须完成六次正式识别导出、三次有效独立剖析及逐类输出对照，本轮尚未启动这些真实运行。

## 当前版本与修改

- 提交基线仍为 `979caeb1cefedd78b2cebac52ca38f28a84d7563`，未提交/推送/合入。
- 补充交付工作树 SHA256：`b0dd82c61618c5b4b2f59a8011b0d43710e5383a9d811ccd1847ef40d0681adf`，规则与首次交付相同。`apps/video-clipper/.runtime/performance-baseline/developer/version.json` 已更新为本补充版本逐文件清单。
- `app.benchmark` 新增 `--no-statistics`，仅允许 `--profile-wait` 或 `--mps-signposts` 表示的独立剖析模式，正式模式使用此开关会明确报错。默认仍开启聚合统计。
- 内部 config 明确传 `statistics_enabled`，worker 按它启停聚合统计；关闭时无 `statistics.json`、无伪造空计数，但 ready/release 和 MPS signpost 独立保留。外部进程资源采样不受此开关影响。报告每组结果记录 `statistics_enabled`。
- 新增3项开关检查（定向测试现共11项），并让既有真实HTTP合成剖析编排验证 `statistics_enabled=false` 已传到 worker 请求。

## 限定清理范围

删除且仅删除旧缓存检查的两份专用源码/清单：

- `modules/rally/experiments/cases.json`
- `modules/rally/experiments/replay.py`

移除 `pyproject.toml` 对该 `cases.json` 的 package-data 项。同步 `modules/rally/README.md`、`modules/rally/experiments/README.md`、`datasets/test-videos.md` 的当前入口与缓存声明；`algorithm-decisions-20261019.md` 仅去掉缺失 `.runtime` 结果链接、说明历史证据不可复验并更新当前验证入口，历史数值与算法决定保留。非归档、非执行历史范围搜索未再发现被删除入口的当前引用。

没有删除原始视频、标注、模型、当前算法实现/参数、`rally_stream.replay_frames` 或既有合成测试；没有做全库清理或新增重复备份。历史 `docs/ai` 与 `backup` 不改。

## 验证与完整证据

- 定向 `apps/video-clipper/backend/tests/test_benchmark.py`：**11 passed in 8.28s**。
- 新增检查：正式模式拒绝关闭统计且不创建输出；实际 worker 在统计开启/关闭两种配置下均发明确 ready/start 事件、进入独立 MPS signpost 上下文，只有开启时写统计文件；产品预测结构保持一致。
- 完整等价后端 `.venv/bin/python -m pytest` 首跑：**102 passed, 1 failed**。唯一失败是未改动的既有实时超载测试：首帧在调用 SlowPredictor 前已迟到0.187秒超过0.08秒限制，因而 `process_s=0` 不满足测试对已调用0.15秒 predictor 的假设。没有改代码、阈值或隐藏此失败。
- 该失败单独复核：**1 passed in 0.74s**；同一源码完整复核：**103 passed, 1 warning in 11.06s**。warning 仍是既有 Starlette/httpx TestClient 弃用提示。上述时序敏感测试存在一次实测波动，后续验收应知悉。
- `git diff --check`、CLI `--help`：通过。相关模块测试命令已包含在完整pytest中。
- `pnpm run test:backend` 的供应链入口阻塞仍沿用首次交付记录，未放宽策略；本轮运行的是该脚本实际调用的完整pytest。

日志均在 `apps/video-clipper/.runtime/performance-baseline/developer/`：

| 文件 | SHA256 |
| --- | --- |
| `backend-tests-supplement.txt`（首跑失败原始输出） | `734487be534122bd29042ef58c6ca80176a10fac4beb214a115f6fe3369ef8a9` |
| `overload-recheck.txt`（单独复核） | `b7b3aa92344a38bedb2ba74f765049f69319b8af87f14816cc3a4df38eeb870a` |
| `backend-tests-supplement-recheck.txt`（完整复核） | `f7ea53c4f96004121838b6a746937d65cf491c192403afb1f629124ae4acb909` |

## 更新后的测量命令

使用主控已准备的 `prepared-models`。六次正式默认开启统计：

```sh
PYTHONPATH=apps/video-clipper/backend .venv/bin/python -m app.benchmark \
  --inputs apps/video-clipper/.runtime/performance-baseline/media/inputs.json \
  --cases A-short A-long C-short C-long D-short D-long \
  --models apps/video-clipper/.runtime/performance-baseline/prepared-models \
  --output apps/video-clipper/.runtime/performance-baseline/baseline \
  --report apps/video-clipper/reports/performance-baseline-results.json
```

三次短片剖析关闭聚合统计，A依次替换为C、D，输出/报告均选新路径：

```sh
PYTHONPATH=apps/video-clipper/backend .venv/bin/python -m app.benchmark \
  --inputs apps/video-clipper/.runtime/performance-baseline/media/inputs.json \
  --cases A-short \
  --models apps/video-clipper/.runtime/performance-baseline/prepared-models \
  --output apps/video-clipper/.runtime/performance-baseline/profile-A \
  --report apps/video-clipper/reports/performance-profile-A.json \
  --profile-wait --profile-timeout 300 --mps-signposts --no-statistics \
  --py-spy-path /private/tmp/smash-performance-tools/bin/py-spy
```

ready/release、py-spy 与 xctrace 命令及管理员边界沿用首次交付的明确协议；`--no-statistics` 不影响它们。正式和剖析均保存真实 `evidence/result.json` 与 `output.mp4`，随后逐类比较原始 `predictions`、`export_ranges` 和实际成片结构/帧数。该对照尚未执行，不能用单测相同或文件SHA相同推断真实输出已通过。

补充代码写入结束，等待主控统一冻结和后续真实测量派发。

# 同轮报告准备：五组已完成证据初步分析

**这是供主控准备最终报告的分析提纲，不是正式交付或验收结论。** 本阶段仅读取已批准的 A-short、A-long、C-short、C-long、D-short 下 `result.json`、`evidence/{result,statistics,benchmark-clock}.json` 与 `resources.jsonl`，以及既有实现。未读取 D-long 活动资源、视频/权重/trace，未运行测试、解码、导出或绘图，未写源码、配置、README 或正式报告。只在本 output 追加。

实现仍按主控冻结的 `b0dd82c61618c5b4b2f59a8011b0d43710e5383a9d811ccd1847ef40d0681adf` 理解。正式报告生成会改变全树文件集合与摘要，最终应核对九次共同实现文件的 SHA 一致，不能要求包含不同报告/结果文件的 manifest 全树 SHA 相同。本阶段未读取各组 manifest，也未独立复核该一致性。

## 最终报告建议组织

1. **结果与适用范围**：六组正式准备/识别/成片/总时间、实际输入容器时长与帧数；三组剖析独立列出，不用于基线排序。明确单次运行、不同来源、非30分钟验收。
2. **流程瓶颈**：六组产品主阶段条形图；识别再按互斥内部主阶段拆分并留出未分摊部分。TrackNet、解码和姿态子项用独立明细，不能再与父阶段叠加。
3. **资源与运行环境**：每组按真实阶段边界展示 CPU、进程 RSS、MPS allocated/driver、含源/不含源目录字节与磁盘剩余。MPS 只覆盖 recognize 上下文，和 RSS 分开；解释实际间隔与短命进程覆盖限制。此处现在只列提纲，未绘图。
4. **证据支持的优化方向**：每项给源文件/统计键、原始秒数与占比、候选措施、整个可消除桶的乐观节时上限、必须补的验证；区分已支持的归因和等待剖析的猜测。避免把原生模型总耗时归为 Python 重写收益。
5. **正确性与交付证据**：九次输入/权重/配置/实现 SHA，输出结构与完整检查；三短统计开启/关闭的原始 predictions、export_ranges、成片结构/帧数对照。旧16例已批准替代，不称旧检查通过。效果准确率与段数另列，不能用性能运行通过代替人工效果验收。

## 五组正式数据初览

所有五组的产品状态均为 `completed`，设备字段为 `mps`；D 的 PoseEstimator 仍按实现走 CPU，不能由该总设备字段推断全部模型使用 MPS。下表时间直接来自产品状态，包含正常 worker 启动、Python imports、权重校验及加载，没有扣净时间。

| 输入 | 产品容器时长 s | 准备 s | 识别 s | 成片 s | 总时间 s | 源时长/总时间 | 原始段数 / 导出段数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A-short | 168.000 | 0.461 | 38.878 | 8.714 | 48.054 | 3.496 | 5 / 5 |
| A-long | 900.120 | 0.480 | 202.197 | 45.095 | 247.772 | 3.633 | 21 / 21 |
| C-short | 180.0003125 | 0.495 | 118.252 | 18.419 | 137.167 | 1.312 | 9 / 9 |
| C-long | 905.0363125 | 0.468 | 523.367 | 61.979 | 585.814 | 1.545 | 30 / 30 |
| D-short | 250.9003125 | 0.486 | 321.121 | 13.476 | 335.083 | 0.749 | 13 / 13 |

“源时长/总时间”只表达本次离线处理比率，不代表实时输入可承载性。C-long 应按实际容器905.0363125秒报告，不能直接填计划窗口900秒；A-long 同理。帧数、末帧归一化时间和原始 PTS 必须保持各自口径，不能用估计帧率补造时间。

本轮 C-short 实际9段、D-short 实际13段，不能直接套用历史确认报告中的 C2=8段、D2=14段作为当前效果结论。两者并非段数相同检查，应等统计开关输出对照，再按相同来源、输入版本、配置和必要人工检查判断差异；目前不将这个差异擅自判为回归或通过。

## 互斥识别主阶段

| 输入 | 模型初始化 s | 视频观测 s | 人物/轨迹 s | 动作分析 s | 回合判断 s | 中间写盘 s | 与产品识别之差 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A-short | 0.0950 | 37.8223 | 0 | 0 | 0.1083 | 0 | 0.853 |
| A-long | 0.0761 | 200.5845 | 0 | 0 | 0.6809 | 0 | 0.855 |
| C-short | 11.6475 | 99.3305 | 5.3898 | 0 | 0.6557 | 0.0009 | 1.228 |
| C-long | 8.7808 | 491.3951 | 20.8280 | 0 | 1.3773 | 0.0035 | 0.982 |
| D-short | 11.2803 | 125.7477 | 0.4455 | 181.9855 | 0.0014 | 0.0047 | 1.656 |

“与产品识别之差”包括识别上下文外的开关/导入/公共校验和调用间隔等，不强行分摊给某一算法。模型初始化桶包含构造器中的导入、加载和设备设置，不等同于纯磁盘读权重时间。

### 可以支持的初步判断

- **A 优先分析 TrackNet 预处理与推理/传输。** 短/长的 `tracknet_preprocess_s` 为9.2771/52.6637秒，占总耗时19.31%/21.25%；`tracknet_inference_and_transfer_s` 为26.4630/143.5394秒，占55.07%/57.93%。回合判断仅0.1083/0.6809秒，即总时间0.23%/0.27%；现有证据不支持优先重写判断规则来获得明显整体加速。成片占18.13%/18.20%，也需在最终报告单列。
- **C 最重的仍是视频观测，而非候选关联。** C-long 视频观测491.3951秒，占总时间83.88%，人物/轨迹20.8280秒只占3.56%；C-short 对应为72.42%和3.93%。`associate`、飞行段拟合等都在人物/轨迹桶内，即使整个桶理想地降到零，节时也最多约20.83秒（C-long）；其中还有 NumPy/SciPy 原生工作，不能直接认作可由 C++/Rust 消除的 Python 时间。
- **C 的 TrackNet 二相采样成本明确存在。** C-short解码5400帧而TrackNet输入10797帧（3599次），C-long解码27134帧而模型输入54267帧（18089次）。计数反映重叠三帧窗口和当前二相方案，不能当作重复解码；只解码一遍。是否可减少推理次数并保留当前效果，尚无本轮证据，不能为省时擅自改采样方案。
- **D-short 首要桶是逐人姿态入口。** 动作分析181.9855秒，占总时间54.31%、识别56.67%；其中 `pose_inference_s`162.0226秒，占总时间48.35%，2432次人物裁剪/调用，平均每次约66.6毫秒。此计时包住 PoseEstimator 入口的图像转换、张量准备、forward及回传，并非纯C++内核、纯Python或纯CPU运算单项。将来可研究逐人调用/预处理、模型执行设备或批处理，但均须真实剖析和结果验证后再定方案。
- **D 二次完整解码已证实，但不应夸大收益。** 两遍各7527帧，累计15054帧；第二遍 `pose_decode_s`7.6129秒、`pose_conversion_s`6.4237秒，合计14.0366秒，仅总时间4.19%。这是理想全部去掉该解码/转换桶的乐观节时上限，不能宣称合并解码会消除整个181.99秒动作阶段。首遍跟踪会使用后续信息，直接并流或缓存原图还要审查上下文依赖及内存代价。
- **D 首遍观测仍有需要原生CPU剖析解释的余量。** 125.7477秒观测内，已列 TrackNet三子项合计66.9761秒、人物检测11.8456秒，剩约46.93秒包含人物描述、光流、缩放、循环和输入等待等。不能把这个差额直接命名为Python开销。
- **中间JSON/NPZ写盘不是目前显著的识别瓶颈。** C/D已计入的中间写盘最大0.0047秒；这不包括成片编码，也不证明磁盘对所有负载都无影响。成片阶段A/C占10.58%至18.20%，D-short占4.02%，需通过原生CPU与IO证据分清编码、读写和等待。

上述“上限”只表示在其他工作不变且整个桶可完全消除时的乐观边界，不是实施承诺或实测收益。模型与解码子项已经嵌套在主阶段，且 FileFrameSource 解码线程可并行，不能把这些秒数再加到主阶段上。

## 资源证据初览

GiB为2^30字节，MiB为2^20字节。RSS为后端及已采到的递归子进程之和，可能重复计算共享页；不能与MPS内存相加。

| 输入 | RSS观测最高 GiB | 目录含源最高 MiB | 不含源最高 MiB | CPU观测最高 % | 资源样本数 / 最大间隔 s | MPS allocated / driver最高 MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A-short | 1.2650 | 83.592 | 16.436 | 546.6 | 49 / 1.0194 | 210.333 / 1108.469 |
| A-long | 1.2818 | 449.338 | 88.922 | 707.0 | 245 / 1.0230 | 291.333 / 1111.844 |
| C-short | 2.2538 | 106.469 | 43.282 | 507.9 | 137 / 1.0264 | 304.211 / 1140.594 |
| C-long | 2.4597 | 491.474 | 159.397 | 676.4 | 578 / 1.0286 | 304.208 / 1141.125 |
| D-short | 2.2250 | 34.279 | 20.662 | 486.9 | 331 / 1.0249 | 232.206 / 1138.422 |

CPU的100%是一逻辑核心，超过100%不代表读错。五组外部资源采样均无读取错误，未见超过1.1秒的间隔；每秒采样仍可能错过短命进程或瞬时最高点。资源树确实采到了后端、worker、FFmpeg；C/D还采到worker下的 `system_profiler` 子/孙进程，原因尚未证明，已包含在测量内，不擅自扣除。

按已保存的产品阶段边界对齐，五组RSS观测最高点均出现在成片阶段。识别期最高RSS分别为A短0.7597、A长0.7660、C短1.7056、C长2.1669、D短1.7161GiB；这支持最终资源曲线必须区分识别与编码，不能只把整程RSS最高点归因于整片观测缓存。

C长识别RSS高于C短是本次观察，但二者来源不同且每组仅一次，不能由此拟合空间复杂度、证明泄漏或推断30分钟要求。MPS样本只覆盖recognize上下文；C-long MPS最大采样间隔2.4891秒（C-short1.3476、D-short1.2654），有明显较长间隔，而不是精确1秒，故MPS值也只能称观测最高。

## 等三短剖析与最终检查才能确认

1. TrackNet的推理/传输桶中，Metal计算、CPU准备、host/device拷贝、`.cpu()`回传同步各占多少；是否受GPU排队或CPU供给限制。不能用该桶总数直接决定改语言。
2. A/C预处理是否主要耗在torchvision resize、格式转换、张量构造或Python调度；py-spy只是Python栈驻留，需与Instruments原生CPU和Metal/MPS时间线互证。
3. D逐人PoseEstimator162秒内部的原生模型、转换和调用开销，以及余下观测约46.93秒的光流/描述/解码等待比例；CPU模型已经由原生算子执行，不等于重写Python就能消除。
4. C关联20.83秒是否由候选规模、拟合次数或Python循环主导；只短片有剖析，不能直接替代长片热点证据。现有计数C短/长分别184/798条关联轨迹、226/911段coherent flights，候选峰69821/254385；不同来源不能当作复杂度曲线。
5. 首次模型构造8至12秒及 `system_profiler` 后代是否为第三方库环境探测或真正模型加载；需要看到调用栈，不能先归因。正式计时包含这些正常开销，不得事后扣掉。
6. FFmpeg编码、源读取和写盘各自占比，渲染期CPU/RSS最高点与进程关系。现阶段仅知render桶和资源曲线，不能证明磁盘瓶颈或特定编码器参数收益。
7. 三次统计关闭剖析是否仍输出与相应正式短片相同的原始 predictions、export_ranges和成片结构/帧数，是否为真实目标PID的有效CPU/Metal/MPS样本。ready/record启动不等于样本有效，必须看导出表和实际PID覆盖。
8. D-long完成后的实际数据、九份输出检查、共同实现文件SHA、输入与权重版本一致性，以及历史8/14段与本轮9/13段的可解释边界。未完成前不更新正式报告状态、不宣称已通过新效果验收。

## 本次读取证据定位

共同根目录为 `apps/video-clipper/.runtime/performance-baseline/baseline/`。每组产品时钟/阶段表来自该组 `result.json` 与 `evidence/benchmark-clock.json`，算法计数和子项来自 `evidence/statistics.json`，段数来自 `evidence/result.json`，资源边界来自 `resources.jsonl`。下列摘要便于后续确认本分析读的是哪一版小证据；本阶段没有改动这些文件。

| 输入 | `evidence/statistics.json` SHA256 | `resources.jsonl` SHA256 |
| --- | --- | --- |
| A-short | `92899ba5061843556fa4a4626077848b82b98117b2a7e930cfd96eb36a3d1fc2` | `02a2b2c69ef4ba752b807616bf307edc055280da48e11c5871547ca94e83ae5c` |
| A-long | `71db349fd598636283b09b9b8e442804a33c115b4062f5a5f123414e29ac7af7` | `f63703f6d087d47cdc7184eb72233d244b7ae243eb9059e506f4fc0515e59d3d` |
| C-short | `ca947e24643015a3ede2379a87e287ccc1e280fbb6e9e52fe7736f3db8397a01` | `a3dfadb2ccef71343a7d0d8c035b9496fb1c3296b055b550c4930f1bf3f91ef7` |
| C-long | `755a4a911a5fc0e7a42062f2deafbb7e8e0248c1199cea97b67d000b929cf6f9` | `cf914174643d6ce5fad36712f6813eec4e945179713bf63bb6d0d4193bfeabd0` |
| D-short | `43ef7d86dcc9b6759286fa244bc9523207739b1b81d40eff992d784f80deff1f` | `029a57f4ecc7bef191f00ef7c5673b05f29217f902e42d6272d2efd2f8ac5da9` |

报告准备阶段到此停止，只写了自身output，继续等待主控派发。

## 历史段数差异的只读核实补充

按主控新增要求，进一步只读现行正式算法报告、标注元数据、现用视频清单、小型配置和既有实现；没有读取原 outputs、backup 源码、视频内容或权重，没有运行模型/解码。**已核实存在输入文件版本差异和观测来源差异，但尚未定位导致区间变化的原因；不能以此直接解释为正常，也不能用后续统计开关相等替代此调查。**

### 输入与窗口

| 项目 | 历史确认报告/标注 | 本轮正式输入 | 可下的结论 |
| --- | --- | --- | --- |
| C2 文件 | `personal-qianfoshan-singles/clip.mp4`，SHA256 `7215d4acf604834d44a5073f8c9a504642322c7528d8077688db932ab8292d74` | `personal-qianfoshan-singles-restored/clip.mp4`，SHA256 `f270602edffd9c6b081cb0463de9aa97f6d1ef3027b0b16d86ab46941bb07f5c` | 路径及文件字节确实不同；未比较解码像素，不能推断是相同帧内容、重封装或不同帧内容。 |
| C2 窗口/时间 | 报告C2声明原视频 `[120,300)` 秒、180000ms、5400帧，`media_time_offset_ms=66.015625`；旧输出使用30fps分数毫秒时间 | `datasets/test-videos.md`仍将现用restored片段列为原视频 `[120,300)`；本轮容器180000.3125ms、5400帧，FileFrameSource首PTS=0、末归一化时间179967ms | 名义窗口和帧数相同，字节不同；旧media offset与当前首PTS/归一化时间不是可直接相减的同义字段，不能据此宣布时间偏移已解释所有差异。 |
| D2 文件 | 路径同为 `d2-check-20261018/clip.mp4`，SHA256 `19d57eefda7817a5940c674468b16df9de9236eb91b522c1d45404d1794a67e8` | 同路径，SHA256 `360e3de1018a9656770ea432c903afba44cff29c0052f03ea65606a5200867fd` | 同一路径已不是历史报告冻结的文件版本。 |
| D2 窗口/媒体 | 报告声明原视频 `[0,250.9003125)`、7527帧、首PTS=0、末PTS=250867ms、1920×1080、`audio_streams=0` | 现用清单窗口一致；本轮容器250900.3125ms、7527帧、首PTS=0、末归一化时间250867ms、1920×1080，`audio_streams=1` | 至少音轨结构发生变化；音轨/容器变化可以改变文件SHA但并不自动意味着视频像素变化，尚未证明它造成模型或区间变化。 |

两个当前原目录片段旁均没有 `sample.json` 或 `validation.json` 小型元数据可继续对应历史参数。历史 reviewed 标注中的 video_sha256 仍分别冻结上述7215…/19d5…旧文件，而本轮输入证据是f270…/360e…，所以不能把历史效果数值无条件用于本轮媒体。

### 配置、court与实现入口

- 已逐字段比较 JSON 字典：现行 `profiles.json.courtside` **完全等于**历史 C 报告 `tail_gap800_growth300` 的 `config`；现行 `personal`、`personal_base`、`personal_options` **分别完全等于**历史 D 报告的 `candidate_config`、`base_config`、`base_options`。因此，目前没有证据把差异归因于这四份已比较配置改了值。其他上游模型/人物/轨迹观测参数尚未获得相同程度的历史对应证明。
- 本轮两份输入 `court=null`。现行C入口因此使用 `player_paths.COURT = [[700,400],[1380,400],[1920,1080],[0,1080]]`（1080p参考像素）选人与跟踪；现行D在null时没有传入显式球场过滤。历史两份报告的C2/D2样本及顶层没有数值court字段，也没有冻结对应模型设备/权重字段，不能确认历史court与设备相同，更不能声称court差异已解释结果。
- 现行调用链是应用worker → `modules.rally.recognize.recognize` → 真实 `observe`/模型/人物跟踪；C进入`scenarios.courtside.predict`，D进入`person_signals`后`scenarios.personal.predict`。`selection.json`逻辑选择仍指向历史C `tail_gap800_growth300`和D `candidate`。
- **历史两份正式报告都明确 `model_inference=false`**：C结果基于冻结的native/shifted/people/flights观测，D基于冻结的signals.npz和players观测，运行的是当时实验入口与.runtime辅助函数；本轮是当前整合入口从视频重新执行全部模型。历史报告留有这些观测及旧代码SHA，但观测现已缺失；未取得旧预处理/选人/跟踪/姿态观测与当前真实推理逐项相同的证据。仅选择名和配置相同不能证明整个输入到区间链路相同。

### 具体原始区间差异

这些差异来自JSON直接比较，**尚未进行画面/标注效果判断**：

- C：历史8段，本轮9段。本轮新增 `149.233–153.533s` 段；历史第4段结束 `68.933333…s`，本轮为 `67.367s`；其后历史一段从 `75.9s` 开始，本轮为 `70.533s`。其他多处起止也变动，不能用“多一段”概括全部差异。
- D：历史14段，本轮13段。历史 `186.3–191.6s` 段在本轮没有对应输出；历史第2段结束 `23.2s`，本轮为 `27.0s`；历史 `48.1–55.8s` 变为本轮 `50.3–55.0s`；另有起止边界变化。是否为对打漏掉、边界退步或其他差异，尚需相应验证，不能仅凭区间列表定性。

本次核实的正式历史证据为：

- `modules/rally/experiments/reports/c-pause-boundaries-20261019.json`，SHA256 `e2cecf480effd6ab1d5e686f227a52fea379ae02f2d38def84df529cf94d8310`；C2样本与选中variant结果。
- `modules/rally/experiments/reports/d-person-context-20261018.json`，SHA256 `a19d5748f7f99a813fdf9003904799be5e337df8c24db7a3803bf5864efe97af`；D2-01样本与candidate结果。
- `datasets/badminton-v1/annotations/reviewed/rally/reserve-{c2,d2}-20261018/full-v1.json`；仅核对媒体路径/SHA，不重评标注。
- `datasets/test-videos.md`；仅核对现用片段与窗口声明。
- `modules/rally/scenarios/profiles.json`，SHA256 `65c20277fe790d6ef648f4693bee985b38c77310803abdd3c2aace81839d7b23`；四份配置直接相等。

**待验收前核实项仍保留**：新旧媒体是否像素/帧选择等价，以及哪个真实观测生成或整合步骤导致当前区间不同。目前材料只足以确认“媒体字节版本不同、相同部分配置、历史缓存判断与当前真实推理路径不同”，不足以定位原因。三短统计开关相等只检验聚合统计开关对当前运行的影响，不能证明本轮输出与历史已接受效果等价。

补充核实到此停止，仍未写实现或正式文档。

# 六正式数据整理交付（正文与源码仍冻结）

按最新派发，仅整理已经完成的六次正式运行，不读取/混用剖析耗时；未跑模型、视频解码、导出或测试，未写源码、配置、正式报告正文、README 或路线图。新增文件只位于批准的 `apps/video-clipper/.runtime/performance-baseline/report-preparation/`，另追加本output。已停止继续生成。

## 公共数据与图表

- [六正式完整摘要JSON](/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/report-preparation/six-formal-summary.json)：每组精确产品时间、输入容器/stream时长、fps与首PTS、算法主阶段及嵌套子项、计数、原始段数、clock、权重与小证据SHA、进程覆盖、实际采样间隔和缺口；不是最终验收状态。
- [六正式摘要CSV](/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/report-preparation/six-formal-summary.csv)：同六组平铺数值，适合后续正式表格与复核。
- [产品/识别阶段耗时图](/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/report-preparation/six-formal-timings.png)：上图直接用产品完整时间，下图只堆叠互斥主阶段与未分摊差值，不叠加解码或模型子项。
- 资源曲线：[A短](/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/report-preparation/A-short-resources.png)、[A长](/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/report-preparation/A-long-resources.png)、[C短](/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/report-preparation/C-short-resources.png)、[C长](/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/report-preparation/C-long-resources.png)、[D短](/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/report-preparation/D-short-resources.png)、[D长](/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/report-preparation/D-long-resources.png)。各含CPU、RSS、MPS allocated/driver、含源/不含源工作目录、磁盘剩余五栏，全部用产品单调时钟对齐，背景和虚线标准备/识别/成片边界。

JSON SHA256：`7cd76dab51219e842c843be4f7fc7b4d247a920ef3628e41ad80b2d25516870b`；CSV：`18ceaf18ef4c7732f8ba227e829b84f63b58e7984e605376f0c5195dbabad647`；耗时图：`df898959182e85c68a405ec64328cbfc8b8b1c7309dc5593b97b7b8e71948c54`。全部CSV/PNG的路径、字节数与SHA在摘要JSON的 `generated_artifacts` 中，小型原始证据路径/SHA在各组 `evidence` 中。

已校对六组CSV与JSON对应值、产品三阶段之和与总时间、产品clock跨度、资源观测最高值与原始结果、生成文件SHA一致；这只是数据整理自检，没有运行产品测试或宣称视频检查通过。已实际查看耗时图与A短资源图，另在排版前查看过C长/D长资源图；最终统一将图例移至图外，并对超过1.5秒的MPS间隔画断线/灰带，避免遮挡或补造缺口数据。

## 时间口径更正与完整六组

**更正前一阶段output中的措辞**：先前表头“产品容器时长”及将905.0363125秒称“容器”不准确，那一列实际来自 `state.video.duration_ms`，即产品使用的视频stream时长。此次JSON/CSV已严格分列：容器时长来自批准输入 `metadata.container_duration_s`；stream时长来自产品状态；fps、首PTS与末归一化时间另外保存，不互相替代。

| 输入 | 容器时长 s | 产品视频stream时长 s | 准备 s | 识别 s | 成片 s | 总时间 s | 原始段数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A-short | 168.091 | 168.000 | 0.461 | 38.878 | 8.714 | 48.054 | 5 |
| A-long | 900.211 | 900.120 | 0.480 | 202.197 | 45.095 | 247.772 | 21 |
| C-short | 180.000313 | 180.0003125 | 0.495 | 118.252 | 18.419 | 137.167 | 9 |
| C-long | 905.144313 | 905.0363125 | 0.468 | 523.367 | 61.979 | 585.814 | 30 |
| D-short | 250.900313 | 250.9003125 | 0.486 | 321.121 | 13.476 | 335.083 | 13 |
| D-long | 611.112438 | 611.1124375 | 0.585 | 834.244 | 49.329 | 884.157 | 31 |

六次产品状态均completed且统计开启，各输入正式运行一次。段数与成功回合数、效果准确率不同；本阶段未做成片解码/结构帧数核查，其状态在JSON中明确写为本整理范围之外。

D-long补齐后，原先优先检查逐人姿态入口的判断仍有支持：动作主阶段501.896秒，其中PoseEstimator入口441.102秒，占总时间49.89%，5837次人物裁剪/调用；第二遍完整解码30.407秒与转换15.819秒，合计46.226秒，占总时间5.23%。主阶段另有视频观测315.845秒、人物/轨迹5.623秒、模型初始化9.242秒。仍不能把姿态入口总时间等同纯Python或纯原生模型内核，也不能把节省二次解码夸大成消除整个动作阶段。

## 资源曲线与采样边界

- 图中CPU的100%为一逻辑核心；后端及实际采到的所有后代保留计入，包括C/D的system_profiler后代，没有扣除。RSS为进程相加，可能重复共享页。MPS allocated/driver单独显示，不与RSS或彼此相加。
- MPS曲线只覆盖recognize上下文，成片区间不延长或补值。外部资源和MPS采样间隔分别统计。外部六组最大间隔1.0194/1.0230/1.0264/1.0286/1.0249/1.0270秒，均无超过1.5秒缺口；MPS最大间隔依次1.0211/1.0233/1.3476/2.4891/1.2654/1.0239秒。
- C-long有4个MPS间隔超过1.5秒，分别1.7598、1.5195、1.7265、2.4891秒；JSON保存每个实际起止时刻，图中标灰带并断线。不称精确每秒连续覆盖或精确峰值。
- 准备阶段均短于一个采样周期，六组外部资源在准备阶段内部均没有样本。摘要将该阶段样本数记0、CPU/RSS聚合记null，没有制造0负载或0峰值。
- 六组RSS观测最高值依次1.2650/1.2818/2.2538/2.4597/2.2250/2.4747GiB，均发生在成片阶段；D-long识别期最高约2.4410GiB。当前曲线能显示内存随流程变化，不能由不同来源短长对照证明内存复杂度或泄漏。
- 工作目录是逻辑文件字节，含源与不含源分开，持久模型缓存不计入；磁盘剩余是全卷级数据，也受其他系统活动影响，不能单靠其变化认定产品IO瓶颈。

## 当前结论边界

固定六正式数据已整理，剖析耗时没有进入基线。源码与正式正文继续冻结；Python/原生/Metal/MPS热点的进一步归因、三短统计ON/OFF、实际目标PID有效样本与成片检查尚由主控按后续证据完成，本阶段不声明全部完成。已知A原生额外全流程补录必须在最终执行次数中诚实列出，不能继续概括为恰好九次；本数据集仅包括六正式，未记录或推断剖析执行总数。

按最新派发，不再扩大历史恢复或把不可比历史结果升级为新的强制验收。前文已核实的新旧输入SHA/音轨/缓存差异与原因未证实的边界保留；本轮不继承历史效果数字，三份真实短片统计ON/OFF标准不回退。当前整理不是最终验收通过，也不替代约30分钟验证或稳定波动估计。

# 2026-10-21 短窗口控制器交付

仅修改 `docs/ai/performance-baseline/controller/` 的控制脚本并追加本output；没有改应用、算法、正式正文或六正式证据，没有启动真实模型、py-spy、xctrace 或管理员授权弹窗。核查完成后停写，真实 C/D 由主控启动。

## 变更与明确运行命令

`profile_runs.py` 现在只接受显式 `C-short` / `D-short`，不传参数或传A均报错；A历史控制脚本与证据保留。可逐个执行，也可明确顺序执行两组：

```sh
.venv/bin/python docs/ai/performance-baseline/controller/profile_runs.py C-short
.venv/bin/python docs/ai/performance-baseline/controller/profile_runs.py D-short
# 或顺序执行：
.venv/bin/python docs/ai/performance-baseline/controller/profile_runs.py C-short D-short
```

这些命令是交付入口，**本开发角色没有实际执行**。目录仍为应用 `.runtime/performance-baseline/profile-control-C` / `profile-control-D`；已存在 profile输出/报告/controls时不会覆盖。后端、worker继续普通UID，只有py-spy通过原有系统管理员授权方式运行。

1. 控制器启动自己的 `--runner` 子模式，导入并运行原 `app.benchmark.main(argv)`，不复制产品runner。C/D完整真实剪辑、py-spy全程100Hz、统计OFF与MPS signpost参数均保留。
2. 子模式包装原 `benchmark.request`：先完成原请求并取得返回，再仅观察GET且包含status/stage的真实产品状态。`stage-current.json` 每次原子更新；`stage-events.jsonl` 只在status或stage变化时追加。两者每条结构严格为 `monotonic_s/status/stage/progress`，不存请求headers或session token。
3. `recording.json` 明确保存这两个文件的绝对路径。控制器据原子current文件跟踪连续阶段，首次观察到选定stage后至少等待4秒，再重新读取新状态确认仍相同且最近GET未过期，才请求附加。
4. C仅找球观测窗口，D找球及人物动作两个窗口；每个使用 `Time Profiler + GPU + os_signpost`、`--time-limit 8s`。trace为 `observation.trace` / `pose.trace`，日志独立为 `observation-xctrace.log` / `pose-xctrace.log`。先确认py-spy附加ready并release worker，native不阻塞最初release。
5. trace保存由后台等待线程处理，主线程继续观察真实阶段及runner；前一个xctrace进程未退出时不启动下一个，避免同时录两份。采样请求区间内阶段变化会留诊断，最终非0；没有required stage、进程提前失败、附加未ready、trace未保存等同样非0并保留证据。
6. `native_windows` 保留请求8秒、首次阶段观察、附加请求、ready、保存结束、返回码、trigger/attach状态及窗口内状态观察。`completed_monotonic_s` 包含保存时间，**不冒充采样结束**；实际范围与阶段覆盖必须由trace TOC和导出样本验证。D姿态窗口GPU/MPS为空可如实保留。
7. 异常时只清理本次runner可定位的普通UID应用子树；不按名字广泛杀进程，不选择其他应用或root sampler树。普通osascript包装器在目标已清理后仍不退出时才停止该已持有的包装器句柄，并留诊断。

## 核查结果

- `profile_runs.py` 的 `py_compile`、两个脚本AST、CLI `--help`、`git diff --check`：通过。
- 新增 `controller/profile_logic_checks.py`，全部使用伪造Popen/UID/时钟及临时阶段文件，无任何真实OS进程、模型或授权。命令：

```sh
.venv/bin/python docs/ai/performance-baseline/controller/profile_logic_checks.py
```

- **5 tests passed in 1.289s**。内部覆盖：原request返回对象不变且无凭证写入；事件只在阶段变化时追加；4秒连续阶段与新鲜GET门槛；8秒instrument命令及跨阶段诊断；A/默认入口拒绝；C与D完整控制模拟成功、native顺序不重叠、py-spy ready先于release、缺阶段明确失败。
- 对照既有 `developer/version.json`，重新计算其中 `modules/` 和 `apps/video-clipper/backend/` 冻结文件SHA，变化列表为 `[]`。没有重新跑产品测试或真实推理。
- 控制脚本SHA256：`profile_runs.py` = `9a02d2ec3e6948ad99548ad2c6abbd1c60d7bdf3c7b8c1fa66d0bd30e8621a3f`；`profile_logic_checks.py` = `99d8d08fa195d33e5cf22e8f68d817f1b4b4a8baebb5ebde55ab22959510f72a`。

本次只证明控制逻辑与冻结边界核查通过，不证明真实附加、8秒TOC有效覆盖、CPU/GPU/MPS样本或C/D输出核对已通过。真实阶段进展、工具权限和trace保存情况仍须主控实际执行后确认。

交付后停止全部代码写入。

# 2026-10-21 最终正式报告开发交付（第一轮，停写待独立验收）

## 范围与版本

按自身 input 最新“最终正式报告实施放行”“C Python采样局部缺失”“主控正文复核”“原生最终有效数据”“公共工具位置整理”完成。仅改任务 worktree 的正式报告、小型报告资产、应用 README、任务 WT 路线图及本 output；没有修改冻结应用/算法/测试/配置，没有改原目录、提交、推送或合入。实施仍基于 `979caeb1cefedd78b2cebac52ca38f28a84d7563` 加已冻结本轮实现，测量前树 SHA `b0dd82c61618c5b4b2f59a8011b0d43710e5383a9d811ccd1847ef40d0681adf`。

正式入口 `apps/video-clipper/reports/performance-baseline.md` 已由协议替换为最终实测报告：先六正式结果与限制，再优化优先级、逐项理想收益上限、资源曲线、Python/原生证据、语言边界，最后固定输入/环境/复跑/精确口径。应用 README 同步真实 API 识别成片完成范围，明确浏览器与重新打包未验证。WT 路线图仍为进行中、实测完成待独立验收；不宣称已独立验收通过。

## 正式证据和结论

- 六正式各一次，产品总耗时 A短/长48.054/247.772秒、C短/长137.167/585.814秒、D短/长335.083/884.157秒。使用原产品准备/识别/成片时钟，不用剖析耗时替代，输入容器和视频流时长/fps/PTS分别保留。主阶段互斥，嵌套与并行子项不相加。
- 10次完整产品处理：6正式 + 3Python统计OFF + A原生额外补录。有效输出检查来自 `output-validation/run-20261021T024238Z/validation.json`，status passed、actual/expected10、issues空、4组原始区间/导出区间/成片结构对照相等。精确写为 worker声明output_duration_ms与区间和差0；实际容器/视频stream/首末PTS在小摘要保留，正文解释A的20ms首帧偏移，没有把声明时长等价为逐帧覆盖。
- Python A passed、C passed_with_sampling_errors、D passed，SVG/log分别17508/17532、22631/22667、46137/46153，错误0/2/0；识别并集4210/12179/32199。C两次get_stack_trace失败、格式行警告、未知根因和局部缺失保留。A握手睡眠10427单列且与识别不重叠；附加前入口导入不在样本内，正式墙钟仍包含。inclusive/self不冒充纯Python CPU时间。
- A原生只采用 `profile-analysis/A/full-native-A-parse1` passed，原生PID42952、Python PID38406是不同执行。完整TOC49.104748秒，识别交集1.504132–39.659329秒；CPU56257/56.257累计权重秒，Metal并集21.873284秒。生成CPU库权重图和目标Metal区间图，非整机GPU利用率。
- C/D仅采用 `profile-analysis/{C,D}/phase-windows-final-v2`：找球两份 passed_with_signpost_tail，D姿态passed，errors均空。C主窗5.095073–13.045600、7.950527秒、CPU10411/10.411、Metal4.634414、MPS65855/裁剪配对union5.652257；D找球1.245430–9.189937、7.944507秒、CPU9559/9.559、Metal2.661880、MPS49367/3.538855；D姿态1.043334–8.956340、7.913006秒、CPU10245/10.245，目标Metal/MPS为0，结合CPU源码路径与BLAS/PyTorch/torchvision栈解释。
- 请求8秒、完整TOC13.045600/9.189937/8.956340、ready→TOC结束∩recognition的主窗分别列出，ready是0.1秒轮询观察值。C/D找球signpost尾部超出TOC0.559535/0.549400秒，含Begin/Event/End与MPSGraph，绝不解释为“仅End异步”。保留探针复现0.568773秒、内部机制未证实、原始诊断/清单SHA；主统计排除尾部，没有改offset/容差。5.1MB逐事件清单保留.runtime，未复制Git。
- 优先验证D姿态入口、公共前处理/推理传输。D姿态入口48.35%/49.89%总耗时是入口桶上界，不是纯内核；第二遍解码与转换只给4.19%/5.23%孤立理想上限。C整个人物轨迹阶段上界3.93%/3.56%，不凭inclusive采样断言解释器瓶颈。模型初始化、内存积累、证据写盘与成片分别列证据、措施、上限/未知和验证方法。
- 语言建议条件化：先窄CPU计时/原生栈确认具体Python循环或对象开销，再做小段等价原型。现有PyTorch/FFmpeg/OpenCV已有原生计算，C++/Rust绑定、数组所有权/拷贝与维护成本须核算，无本轮证据支持全模块迁移或二者谁更快。
- 六资源图保留进程树/CPU单核口径/RSS共享重复/MPS独立、识别覆盖和观测峰值；C长MPS四处>1.5秒缺口最长2.489秒，断线标灰。不同来源短长与单次测量不能证明复杂度、稳定波动、泄漏、最低硬件内存或30分钟验收。旧缺失16缓存检查已批准替代，不称其通过、不继承历史效果。

## 本阶段修改文件

- `apps/video-clipper/reports/performance-baseline.md`
- `apps/video-clipper/README.md`
- `docs/plan/roadmap.md`（只任务WT性能条目）
- `docs/ai/performance-baseline/developer/output.md`

资产目录33文件合计 3134202 字节（约3.13MB），原视频/trace/大XML/逐秒资源未复制：

- `apps/video-clipper/reports/performance-baseline/A-long-resources.png`
- `apps/video-clipper/reports/performance-baseline/A-short-resources.png`
- `apps/video-clipper/reports/performance-baseline/C-long-resources.png`
- `apps/video-clipper/reports/performance-baseline/C-short-resources.png`
- `apps/video-clipper/reports/performance-baseline/D-long-resources.png`
- `apps/video-clipper/reports/performance-baseline/D-short-resources.png`
- `apps/video-clipper/reports/performance-baseline/evidence-index.json`
- `apps/video-clipper/reports/performance-baseline/implementation-freeze.json`
- `apps/video-clipper/reports/performance-baseline/inputs.json`
- `apps/video-clipper/reports/performance-baseline/native-A-artifacts.json`
- `apps/video-clipper/reports/performance-baseline/native-A-cpu.png`
- `apps/video-clipper/reports/performance-baseline/native-A-metal.png`
- `apps/video-clipper/reports/performance-baseline/native-A.json`
- `apps/video-clipper/reports/performance-baseline/native-C-observation-artifacts.json`
- `apps/video-clipper/reports/performance-baseline/native-C-observation-cpu.png`
- `apps/video-clipper/reports/performance-baseline/native-C-observation-metal.png`
- `apps/video-clipper/reports/performance-baseline/native-C-observation.json`
- `apps/video-clipper/reports/performance-baseline/native-D-observation-artifacts.json`
- `apps/video-clipper/reports/performance-baseline/native-D-observation-cpu.png`
- `apps/video-clipper/reports/performance-baseline/native-D-observation-metal.png`
- `apps/video-clipper/reports/performance-baseline/native-D-observation.json`
- `apps/video-clipper/reports/performance-baseline/native-D-pose-artifacts.json`
- `apps/video-clipper/reports/performance-baseline/native-D-pose-cpu.png`
- `apps/video-clipper/reports/performance-baseline/native-D-pose-metal.png`
- `apps/video-clipper/reports/performance-baseline/native-D-pose.json`
- `apps/video-clipper/reports/performance-baseline/output-validation.json`
- `apps/video-clipper/reports/performance-baseline/python-A.svg`
- `apps/video-clipper/reports/performance-baseline/python-C.svg`
- `apps/video-clipper/reports/performance-baseline/python-D.svg`
- `apps/video-clipper/reports/performance-baseline/python-summary.json`
- `apps/video-clipper/reports/performance-baseline/six-formal-summary.csv`
- `apps/video-clipper/reports/performance-baseline/six-formal-summary.json`
- `apps/video-clipper/reports/performance-baseline/six-formal-timings.png`

`evidence-index.json`汇总原始绝对路径、输入/权重/输出/逐秒资源SHA、native trace文件树SHA、解析摘要/索引来源SHA、Python来源及33资产中的其他小文件SHA。原生各源artifact-index小副本保留原始trace/XML文件树或文件SHA索引，不重复大原始数据。

公共解析/输出检查工具引用使用新 `docs/ai/performance-baseline/controller/{native_profiles.py,python_profiles.py,validate_outputs.py}`，正式正文未引用旧角色通信目录源码；历史记录不改写。

## 最终核查与未执行项

1. `implementation-freeze.json`核对147个共同非文档实现/测试/配置/工具文件：当前WT与baseline/profile-A/profile-C/profile-D/profile-native-A五份manifest均匹配，differences全空。报告/资产新增不被误判为所有manifest全树hash必须相同。
2. 六正式表格逐行与精确JSON核对、9份原始摘要/CSV/PNG副本逐字节相等；全部33资产JSON可解析、证据索引各资产SHA一致；四份native小摘要来源summary/index SHA一致，采用明确有效/受限状态，errors空。
3. 正式报告、app README、WT roadmap全部当前本地链接存在，native待补标记已清除；逐张目视检查7张正式耗时/资源图、8张native CPU/Metal图，图例、范围、单位与空姿态GPU含义可读。
4. `app.benchmark --help`、`controller/profile_runs.py --help`、迁移后的 `native_profiles.py --help` 与 `python_profiles.py --help`均成功。注意 `validate_outputs.py`不解析--help：本角色额外尝试时进入main，但创建新run目录即被只读沙箱拒绝，未创建目录、未开始解码；已告知主控且未提权重试。正文明确该工具直接运行、无--help入口；本次不把它记为新的输出检查结果。
5. `git diff --check`通过；review了本次README/roadmap差异与最终正文/小摘要。此阶段未重跑模型、采样器、trace导出、输出解码或产品测试，未安装或改依赖。原测试/控制器合成核查结果见前次交付，新的关键验收由主控派发独立角色。

正式与剖析复跑命令、明确ready/release协议及当前controller调用入口已在正式报告末段给出；本轮已有路径拒绝覆盖，新实验须使用新的证据目录/工作树。后续需独立功能、代码和文档验收；报告不作为其通过结论。

## 交付定位与停止状态

- `apps/video-clipper/reports/performance-baseline.md` SHA256 `0f66a190566f93bbb5ac16c1e4c4bd34501d59bc7b2d75d4322ffcc12b873e83`
- `apps/video-clipper/reports/performance-baseline/evidence-index.json` SHA256 `4f9094f3dad994c362224cf4b8c9b2a4e0440e2cf933d06671bd5e121121ad60`
- `apps/video-clipper/README.md` SHA256 `8d5a121de4dfeadf208162ecb81c28a38c80f7babbf447745c74dda4e7b552b8`
- `docs/plan/roadmap.md` SHA256 `a9041d0c3f85a295e92ca7c48237ad4e292b446175eda237ee39e86a870e5159`

本轮报告与资产写入完成，现停止全部写入，等待主控冻结独立验收与下一次明确派发。
