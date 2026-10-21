# 原生剖析导出与汇总准备，第一轮
读 ../task.md、根AGENTS、必要实现。禁止读developer/verifier/其他角色通信目录。当前正式测量仍执行，本轮仅写脚本及自身output，不执行xctrace export、XML全解析、哈希大文件、测试/解码或其他CPU重任务，不改源码或正式报告。
任务：在本目录准备 native_profiles.py，稍后主控授权后对三份真实trace顺序导出并汇总。现有结构证据可仅读 apps/video-clipper/.runtime/performance-baseline/profiler-preflight/ 的3种XML各前16000字节理解真实schema（不要全parse/扫描），未确定的字段清晰报错，不泛化猜测。
正式证据：.runtime/performance-baseline/profile-control-A、-C、-D，每处recording.json含target_pid/target_uid/实际命令/时刻；native.trace为原始bundle，python-flamegraph.svg为py-spy原始火焰图。当前这些目录未开始。
脚本授权执行后：等待控制器确认.trace保存完成（本脚本只接已完成trace，不读活动录制），每个trace导出toc及time-profile、metal-gpu-intervals、os-signpost，命令xcrun xctrace export --input ... --toc --output ...，或 --xpath '/trace-toc/run[@number="1"]/data/table[@schema="time-profile"]' 等。每条命令保存日志与returncode，失败保留证据并非0退出，不伪造通过。输出均写应用.runtime/performance-baseline/profile-analysis/<A|C|D>/。
XML用ElementTree实际id/ref索引解析每个字段。CPU/GPU/signpost都必须按recording.json目标PID筛选，原始GPU/标记表会包含其他系统PID。记录总行数、目标行数、排除数及未解析字段诊断。
CPU time-profile只汇总目标Running且weight>0样本：样本数、采样时间首尾、weight秒（累计CPU时间估计，跨线程可大于墙钟，不能称墙钟占比）；leaf符号/二进制exclusive权重top50与inclusive符号top50（同栈递归同符号去重，inclusive不能相加）。保留全二进制leaf占比，以及若干具体C++/OpenCV/Metal函数示例。不要把函数名里含torch就等同Python执行。
Metal GPU只取目标Active状态有效start-time/duration，求所有重叠区间的并集（不可直接相加），保存分状态数量、范围及Active union秒；分队列/嵌套都先全局并集。分母若做占比只能是本次trace观测时间范围，明确不是正式baseline GPU利用率。
os-signpost只汇总目标PID，另单列subsystem=PyTorchMPS的有效事件/区间数量、names/messages/实际schema值，若可计算interval亦须说明嵌套不可相加。三项目标证据均应非空，否则失败。不要把全系统行数当目标有效数据。
生成summary.json及artifact-index.json：包含导出XML/TOC/日志、原始py-spy SVG和native.trace文件树的每文件size/SHA（目录SHA由相对名及内容SHA规范排序生成），保留原始位置，不复制大trace。当前只编写，syntax compile，停止并回报。

## 主控补充：排除附加等待的识别窗口（仍仅准备）
A真实剖析已运行一次。控制器最初期待TTY的Recording文案，实际pipe模式只输出Ctrl-C to stop the recording，已保留同一target/samplers手动release，未重跑/再次鉴权。A含约134s准备/等待，正式baseline不受影响。controller/profile_runs.py仅控制脚本已修正，其余C/D尚未跑。
每份recording.json将有 monotonic_to_epoch_offset_s、release_epoch_s，三profile的evidence/benchmark-clock.json有benchmark_start（工作进程monotonic）与rendering（同机后端monotonic）。toc run/info/summary/start-date为带时区ISO日期（可只读controller/profiler/probe-toc.xml中的summary节点看结构；不要输出environment值，原始TOC含环境只保存在忽略runtime）。
请添加识别窗口分析：起点benchmark_start，终点rendering，按recording offset映射为epoch，再减toc.start-date得到trace-relative秒。记录映射方法、TOC毫秒精度限制、起止窗口与trace duration包含关系。若实际trace数据时间原点验证不一致须报错待主控核实，不猜测。原始各表总/目标行数和全范围数据保留；用于CPU热点、GPU Active并集的主要统计仅取识别窗口（GPU区间裁剪后并集），单列目标窗口外数据。os-signpost仍可全目标汇总并单列窗口内MPS数量。
Python原始SVG含等待，不编辑原文件；如摘要提其占比，必须说明Python帧驻留而非纯CPU，A应聚焦recognize子树，不能把handshake等待当算法热点。不需要重画/自行重建py-spy火焰图。当前只更新脚本并syntax，仍等三录制保存后主控授权执行。

## A原生补录与明确路径（主控恢复）
A首轮Python捕获有效（17532samples/0errors），但全套Metal System Trace额外活动整理长期不结束，raw约9GB，恢复export报Document Missing Template Error。已停止该xctrace并保留native-unfinished.trace/failed-native-finalization.json/save-sample.txt/xctrace.log/recording-python-pass.json。它不能作有效原生交付。
新精简探针 Time Profiler模板 + GPU instrument + os_signpost 已实测正常保存，并导出targetPID CPU594行、GPU3064行、PyTorchMPS18384事件，公共证据app.runtime/focused-preflight/verified.json。
A现仅补录一次原生（没有再启动py-spy或管理员授权）：runner目录app.runtime/profile-native-A/A-short；新native.trace仍在profile-control-A/native.trace；新recording.json的target_pid是原生A新PID，python_capture字段明确原始Python不同PID38406与关联SVG/metadata路径，勿声称同一进程/同次捕获。
C/D控制器已改用同一验证组合。三recording.json均提供 native_case_directory、native_benchmark_clock_path，请窗口总是从这个明确路径读取，不再硬编码profile-A/A-short（A两轮时间不同会造成错误映射）。Python数据归属metadata.python_capture，原生筛选用target_pid。
仍仅更新脚本/syntax，三有效原生均保存后主控再授权执行。最终报告与索引明确六正式各一次+三Python剖析+A一次原生补录（10次完整处理），保留失败诊断；不得冒称仍9次或重复六正式。

## 执行授权：仅A完整补录（2026-10-20最新）
A2的native-focused.log已明确Recording completed / Output file saved as native.trace，native_recovery_A.py exec60506已exit0且runner_returncode=0/trace_returncode=0。现在可对 A 执行：.venv/bin/python docs/ai/performance-baseline/profile-analysis/native_profiles.py --controller-confirmed-complete --cases A --run-id full-native-A。使用正常本机权限。不得碰未开始的C/D，不启动模型/采样器，不读其他角色通信。
原生A完整采集可交付，新增5秒真实TrackNet窗口工具探针正在执行作方案诊断（不是正式剖析）。用户窗口选择尚未答复，C/D暂不启动。
请真正导出/解析/哈希A的数据，遇到真实schema/格式不符先保留失败证据，再按实际数据修本目录分析脚本并复核（不改应用源码/标准、不猜测兜底），报告每次结果和有效输出索引。原始environment留忽略runtime，不复制到docs/ai正文。小结给出targetCPU/GPU/MPS有效性、窗口验证、未解析ref/errors、原生CPU热点/Metal并集；保留PythonA1与nativeA2不同PID/回合相同输入的边界。

### A解析修复后复用已有导出
首次 full-native-A 的4个export返回0且文件存在，parser的UnboundLocalError是分析脚本问题。保留失败summary和日志，修复后从同目录export-status.json引用原XML重新parse/生成小型retry summary与index；不要重导出/复制大XML。不使用后续误触发的partial retry目录，记录实际中断即可。允许增加明确的复用现有exports解析参数，不引入额外兼容猜测；SHA索引指向原始导出路径。新分析summary单独路径供主控/报告引用，不能覆盖失败记录。

## 2026-10-21 短窗口授权与预检核实（第一轮）
用户已同意按阶段短窗口。现在仅做两项：1验证已有CNN5秒探针apps/video-clipper/.runtime/performance-baseline/cnn-window-probe/，从ready.json目标PID、execution.json/日志/TOC和已导出三XML按实际id/ref解析，确认目标CPU/GPU/MPS非空、正常保存、普通UID，写本目录/自身output及.runtime小型verified.json。不运行模型、不采样、不重export探针。2准备解析C/D窗口支持，仍不执行尚未产生的C/D数据。
控制器recording.json继续有target_pid/uid/native_case_directory/native_benchmark_clock_path/python_capture/monotonic_to_epoch_offset_s；新增native_windows数组，每项name='observation'或'pose', stage, trace_path,trace_command,requested_duration_s:8,trigger_observed_monotonic_s,attach_requested_monotonic_s,ready_monotonic_s,completed_monotonic_s,trace_returncode。C observation、D observation+pose。TOC startdate/duration为实际trace覆盖；整段recognition不在trace内是正常，不可沿用A full window包含要求。计算实际trace与benchmark_start→rendering区间交集作为分析窗，保留整段映射端点/本trace覆盖范围与所属phase，不声称覆盖全程。真实stage-current/events供核对，若跨阶段应明确诊断不能掩盖。CPU/GPU/MPS按目标PID过滤；observation三表都应非空，Dpose要求CPU非空，GPU/MPS真实空有效且说明CPU模型路径。原点检查与XML ref诊断仍必须通过。CPU估算累计weight非墙钟；Metal union非利用率。
保留已成功A解析及其索引不变，新参数显式选择 --windows，C/D分别按native_windows导出/解析/hash索引，且每窗口可独立复用成功导出避免重复大文件。不复制raw trace/XML。可以复用现有解析函数，减少新增重复代码，别为了兼容旧不真实结构泛化。先验证探针并实现/syntax，写output并等待执行授权。禁止读developer/verifier/其他角色通信，不改应用源码/正式报告。

### 确定的阶段证据路径与结构
controller记录于 profile-control-C/stage-events.jsonl、stage-current.json（D同理），recording.json新增 stage_events_path 和 stage_current_path 明确绝对路径。每条事件 {monotonic_s:number,status:string,stage:string,progress:number}，仅在状态或阶段变化时append；current每次GET更新同结构。trace原点epoch减offset转monotonic，与events阶段进入→下一事件判定覆盖；若trace结束后没下一阶段且整个job已completed用最后状态事件时刻封闭。不要读取token等请求参数。metadata缺路径/事件字段明确失败；记录实际trace覆盖阶段，若窗口跨所选阶段边界应诊断而非自行假定。

### 主控复核补充（C/D启动前）
--windows必须要求C恰有observation、D恰有observation和pose，不能缺Dpose仍标通过。target_pid>0、target_uid为当前普通用户且非0；recording runner_returncode/py_spy_returncode须0再分析。每窗source_dir在try前初始化，避免前期失败后索引分支未定义遮蔽原诊断。现在仅最小修正/syntax，C/D完成后再授权执行。阶段解析允许CPU pose无目标GPU/MPS，但不能将全系统行数当目标。

## C/D实际分析执行授权（2026-10-21）
主控真实controller exec30703已退出0。C目标50312 UID501、D目标51087 UID501，runner/pyspy退出0，C observation与D observation/pose三trace均退出0且日志Output file saved，无控制diagnostics。全部应用处理已结束，可现在执行native_profiles.py --controller-confirmed-complete --windows --cases C D --run-id phase-windows-v1。只处理已保存C/D，不重解析/重hash A或启动采样器/模型。实际schema问题留失败诊断，按数据最小修复本目录解析器，成功XML须复用不重export。自身output记录有效输出索引和各窗目标CPU/GPU/MPS有效性、实际TOC覆盖/阶段/refs、热点，完成后停写回报。

### 主控看到首次窗口分析失败，须核实后修复
三窗首轮已写failed摘要：C/D observation的os-signpost目标时间尾分别13.605134833 vsTOC13.0456、9.739336875 vsTOC9.189937；同时三窗都报TypeError int不可下标。请保留首次摘要/exports，取得具体 traceback定位TypeError（可能analysis中含target_pid标量，按实际返回结构核实，不泛化兼容）。修复仅复用成功XML，生成phase-windows-parse1新小型目录/索引，不重导出或复制大文件。
os-signpost越过TOC约0.55秒不能直接加宽容差/改时间原点。检查实际target事件种类、具体时间/消息、末端是否End/异步流刷新，CPU/GPU表时间已在TOC内；依据真实数据解释采集与异步signpost尾部时间边界，主统计仍裁剪实际TOC∩recognition窗口，窗口外事件独立保留，不把它们加进CPU/GPU区间。如能证明仅某些工具延迟/缓冲事件可报告其原始范围与截断，不伪称全表原点全部包含；原因不明则保留失败与待核实，请主控决策。必须分别保留原点一致性与边界溢出事实，不能只让validate返回passed掩盖问题。A成功数据不动。

## 原生窗口边界事件专项核实与恢复授权
主控已核对与本地torch2.8对应的官方v2.8.0源码：https://raw.githubusercontent.com/pytorch/pytorch/v2.8.0/aten/src/ATen/mps/MPSProfiler.mm ，addProfilerCompletedHandler在MTLCommandBuffer完成回调中调用endProfileExecution，后者发出End interval（原文423–445、247–277），wait_until_completed=False不会每算子等待。这支持End具有异步完成语义，但不能据此断言Instruments具体缓冲/导出原因已被证实。
下一步只用成功XML，专项解析所有目标PID时间超过TOC终点的signpost，列实际数量、event-type/subsystem/name、每个End的signpost-ID与对应最近未配对Begin timestamp、是否Begin在TOC内部且End>Begin，给前10个例子并保存完整边界列表。核实CPU/GPU原始范围始终在TOC内，stage窗口匹配，未解析引用0。不调整任何时间offset或容差，也不重导出/模型/采样。
若事实确认为“全部超界仅PyTorchMPS区间End，均配对到TOC内Begin”，则原先“所有signpost时间都必须在TOC内”是解析工具额外加入的不适用假设，可按跨窗口区间收尾语义处理：保留within_toc_trace_duration=false与原始尾部范围/数量，新增boundary_event_validation=paired_interval_end_tails；CPU/GPU原点仍严格检查，MPS主要计数/区间只取TOC∩recognition，配对区间也必须裁剪后求并集；不得将全target的MPS interval union当窗口并集。状态可用passed_with_boundary_events，清楚报告边界End已排除/截断，不称三表全范围都在TOC内或异步时延就是GPU运行时间。解释是源码支持的语义判断、不是已证实xctrace内部根因。
若有越界Begin/Event、无法配对End、或Begin也在窗外，则仍failed，不做这个分类，回报实际缺口。保留phase-windows-v1及retry1全部失败小记录，复用原XML生成新phase-windows-parse2目录与小索引。Dpose已passed可复用其分析索引，不需要无意义重parse。主控收到后亲自复核，并交独立验收确认边界处理是否支持报告结论。

### 以现有附加就绪标记定义8秒分析窗，保留完整TOC
主控用既有recording就绪单调时刻与TOC精确核对：C observation ready为trace-relative5.095072746s，TOC终点13.0456，ready→终点7.950527254s；D observation为1.245430231→9.189937即7.944506769s；Dpose1.043334246→8.95634即7.913005754s。TOC还包含0.96–5.10秒工具附加期，所以完整TOC9–13秒不应混作请求8秒的主要分析窗。
在本轮复用解析时，C/D主要窗口起点取max(TOC开始、benchmark_start、recording该窗ready_monotonic_s+offset)，终点取min(TOC结束、rendering)，属于“附加确认就绪之后至实际采集结束”的已有明确边界，不按热点挑选时段。完整TOC范围、ready映射、附加期样本与实际7.91–7.95s分析跨度都保留；就绪日志由0.1s轮询观测，注明误差口径。Dpose也以此窗口重新parse以使三窗一致，但复用既有XML/trace索引，不重导出/大hash。A full不变。
边界End专项仍对完整TOC越界事件核实，再将主统计严格裁剪到这个实际分析窗，MPS事件/interval union也裁剪，所有界外数据单列。阶段核对同样覆盖主要分析窗，完整TOC阶段保留。此约定落实用户约5–10秒窗口要求；不能把TOC13秒冒称8秒或不说明附加期。

## 受控探针已复现跨表停止边界差异，按实际窗口报告
主控刚用已有cnn-window-probe三表解析器复核（没有新采样/鉴权）：同样的独立12秒持续TrackNet、xctrace请求5秒工具探针，TOC7.890086秒，但目标signpost范围[4.337329125,8.458859166]，超出0.568773166秒，TOC内MPS23232事件。公共stop-boundary-check.json已存该诊断。C尾0.559534833、D尾0.549399875。该现象在先行受控工具探针与两个正式原生窗口可重复，不能再用“run duration必然是每张导出表的完整范围”这个未经验证的假设把全部窗口判无效。CPU/GPU严格原点校验仍必须通过；不要改offset/容差，也不声称已经知道xctrace缓冲内部原因。先前End-only假设已被真实Begin/Event反证，保持该失败诊断，不复用其解释。
用户要求有效CPU/GPU/操作标记和明确短窗口，不要求导出表不得包含窗口外数据。对有足够目标PID、正确stage、refs0、CPU/GPU有效、主窗口内MPS非空的observation，可将证据有效性记录status=passed_with_signpost_tail，并在trace_time_origin_validation单列：CPU/GPU passed；os-signpost within_toc=false，tail raw范围/按type/subsystem/name数量及outside事件索引；signpost_cross_table_stop_boundary='reproduced_in_controlled_probe'。此状态明确局部观测证据有效但导出表范围大于TOC，不能伪称三表全范围校验通过，也不能把tail加入主统计。完整配对/原始范围和早先failed记录不删。
MPS主窗口计数严格ready→TOC约7.9秒，配对interval union裁剪到该窗，原始全范围union单列。原始trace与XML保留、不要额外导出/大hash。复用现有XML生成phase-windows-final（三窗一致，Dpose passed），小索引关联初次raw哈希；summary包含受控探针诊断路径/hash与上述状态解释。若原来CPU/GPU/stage/必要MPS/refs任一不合格仍failed，不能以tail分类兜底。
最终独立验收须审查这条基于实际工具数据的边界处理及报告结论是否足够；主控不会仅因summary变为上述状态就判任务验收通过。请实施最小工具口径修正、运行复用分析、写明所有值/限制后停写回报。

### 最终冻结前两处机械修正（数值窗口不变）
主控已读phase-windows-final，三窗指标/状态/阶段均按预期。再做两处最小修正后停写：
1. validate_trace_time_origin的time-profile目前读top-level target_sample_time_range_s，这是窗口别名，不能证明“原始CPU全范围严格在TOC内”。改读analysis.time_profile.full_trace.target_sample_time_range_s；本次三窗实际完整范围分别[0.247288166,13.044105166]、[0.249635083,9.189936750]、[0.241112583,8.955807791]均已在TOC内，所以不会改变窗口数值或通过状态，但保证检查语义真实。
2. signpost-boundary-events.json为4.9MB原始逐事件数据，移到应用.runtime/performance-baseline/profile-analysis/signpost-boundary-events.json（原字节不变）。本目录代码中的所有当前引用、摘要/索引的full_event_list_path及哈希路径改指新绝对位置；自身output留迁移映射，旧失败历史摘要可保留原样作历史，但所有当前有效索引必须可达。不要在Git/docs/ai保存整份原始边界表，不新增重定向；最多留小型路径/SHA/数量摘要。正式报告开发尚未使用旧final，因此现在调整不破坏交付。
复用原XML（非前次新小索引缺少实际files的中间层，以首次phase-windows-v1作--reuse-from），生成phase-windows-final-v2三窗，不能覆盖任何先前尝试/重导出/大hash。确认origin CPU原始完整范围、raw边界路径存在及SHA一致、窗口数值/状态与上轮不变，syntax+diffcheck，output回报后停止。这就是最终交付路径，后续由主控冻结独立验收。
