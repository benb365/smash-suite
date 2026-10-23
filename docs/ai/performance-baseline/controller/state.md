# 控制器恢复状态
- 任务worktree /Users/bytedance/.codex/worktrees/performance-baseline/smash-suite，分支 codex/performance-baseline，基线979caeb1cefedd78b2cebac52ca38f28a84d7563；原目录仅roadmap认领变更，原outputs未写。
- 第一轮开发已停止，见developer/output.md；完整等价pytest100通过，pnpm入口被watchpack供应链策略拦截，不改锁/策略。代码/统计/真实HTTP runner已实现，未执行六正式和三剖析。CLI为PYTHONPATH=apps/video-clipper/backend .venv/bin/python -m app.benchmark。
- 媒体角色baseline_inventory正在完成输入像素/PTS映射与连续性复核；六文件EOF+完整音视频解码已通过，media/inputs.json尚待角色最终输出。已裁定接受streamcopy实际源窗口A599.96–1500.04/C115.07–1020.007/D0–610.979；理由见media/input.md，不能省略剩余预检。
- 模型已从原.runtime/product-data/models只读复制到 apps/video-clipper/.runtime/performance-baseline/prepared-models/，三SHA均与assets.py固定值一致，不需下载。此路径与developer输出示例models路径不同，真实命令用prepared-models。
- 工具探针全部实际测通：controller/profiler/verified.json；py-spy0.4.2位于/private/tmp/smash-performance-tools/bin/py-spy，非root失败，sudo-n需要密码，使用osascript系统管理员授权实际成功299samples/0errors。只有采样器root，probe uid501。CPU+Metal+os_signpost trace真实target数据非空。大原始文件在app .runtime/performance-baseline/profiler-preflight。time-profile.xml额外导出949行、具体C++/Metal函数栈有效，尚未追加verified.json该字段。
- 所有探针已结束/清理，无正式测量进程。
- 旧16例回放所需35份观测全部不在本机（含原模块.runtime、原outputs定向恢复、原根.runtime和A2绝对缓存）。replay/output.md记录盘点。已向用户异步询问：用三真实短片正式/剖析作为统计开关对照替代（不增加9次）或保留16例要求等待恢复。用户答案尚未收到，不得擅改验收或假称回放通过。
- 若用户同意替代，需要下一轮开发为profile选择关闭聚合统计、保留signposts与握手，以与baseline开统计的真实predictions/export_ranges对照；当前profile默认统计仍开。正式6次可继续独立准备，不在运行中修改源码造成版本混用。
- 后续：媒体passed -> 确认用户回放选择/必要补丁与测试 -> 冻结完整实现 -> 按6输入顺序真实MPS正式运行（正常本机权限，模型参数/CPU姿态线程原样） -> 3短剖析握手附加py-spy和xctrace后release。每次profile-ready提供pid/release_file。预检已测xctrace命令: Metal System Trace + --instrument 'Time Profiler' --instrument os_signpost。必须等采样实际开始后release，结束后等trace保存再export（早导出会malformed，已验证）。
- runner生成speedscope命令，主控可选择py-spy flamegraph SVG直接输出以提供可查看图；若保留speedscope则需实际查看入口。建议profile采样SVG并保留.trace。只附加本任务UID501 PID。原生XML需解析id/ref，GPU/os-signpost含系统其他PID，分析必须筛目标；GPU重叠区间不能简单相加。
- 真实证据完成后派developer写正式报告/资源图/固定输入清单/优化与C++Rust分析（此时可改文档，代码若改变需复核），主控冻结验收版本 -> 独立新上下文verifier按skill验收功能/代码/文档。验收后任何代码变化需复验。通过才本地提交，保留worktree，不推送不合入。若用户保留旧回放要求且数据缺失，不能验收通过。

## 2026-10-20 最新状态（覆盖以上旧阶段信息）
- 用户已批准旧缓存替换验收及限定清理，task.md为当前授权。profile --no-statistics已实现。
- 补充后端检查103 passed（11.06s）；pnpm入口供应链策略阻塞仍保留，不改策略。
- 实现冻结SHA b0dd82c61618c5b4b2f59a8011b0d43710e5383a9d811ccd1847ef40d0681adf，357文件，详见pre-measurement-freeze.json；九运行期间不改实现。
- A/C全窗逐帧像素与PTS映射已完成，D进行中；continuity角色独立完成正式连续性抽查。inputs.json存在但仍为中间稿，不能因passed字样提前运行，等待media最终交付及公共continuity summary。
- CPU time-profile符号栈已实际导出949行/18353帧；工具均测通。尚无正式测量。

- 六输入预检已最终通过，所有素材CPU工作停止。正式基线已于2026-10-20 21:07左右启动，exec会话34478，caffeinate仅防睡眠，普通用户/MPS。结果目录 app .runtime/performance-baseline/baseline，报告 apps/video-clipper/reports/performance-baseline-results.json。尚不能判定完成；顺序A短长/C短长/D短长。

## 测量进度与恢复（最新）
- exec34478仍运行，五正式完成：A短48.054s，A长247.772s，C短137.167s，C长585.847左右s，D短335.1s；D-long进行中。真实结果JSON为准，均device=mps/balanced，尚无重跑。不要重复执行已完成正式输入。
- D短pose_inference162.0s，pose_decode7.61s，action_analysis181.99s，2遍共15054解码帧，2432裁剪/姿态调用。C长关联20.83s，观测491.40s。子项嵌套不能加父阶段。
- profiler控制脚本 controller/profile_runs.py 已准备并syntax通过，尚未执行；六正式结束后普通用户/正常本机权限运行 caffeinate -i .venv/bin/python docs/ai/performance-baseline/controller/profile_runs.py。它写profile-A/C/D及profile-control-A/C/D，osascript仅提权py-spy，等待xctrace Recording和py-spy Sampling process后release。必要时根据真实日志修复控制脚本（docs/ai，不改实现），保留失败附加诊断；没有release不能算完整剖析。
- validation/validate_outputs.py 由低成本 replay_recovery准备并补齐断言，尚未执行。九真实结束后授权其核对所有视频SHA、完整AV解码、实际帧/PTS/结构、资源PID/计时、三组统计ON/OFF原始predictions/export_ranges严格相等；输出在app.runtime/output-validation。
- baseline_inventory正在profile-analysis/input.md限定下准备 native_profiles.py：仅读preflight XML前缀看schema，写脚本，不实际export/全parse/重任务。三剖析均结束后再授权顺序导出3schema并按目标PID过滤、CPU权重/Metal Active并集/MPS标记与hash索引；输出app.runtime/profile-analysis。
- baseline_developer已获报告准备阶段授权：只读五完成小型JSON/资源与实现，只写developer/output.md初步分析，不写正式报告/README/源码，不跑重检查。等全部证据完成后再授权正式报告和曲线。
- 六输入公共continuity summary最终passed，media/output.md给完整来源校验；D原始PTS vsFileFrameSource差0.133s是归一化起点，不能误判异常。所有素材重处理已停止。

## 六正式已完成，剖析A保存中（覆盖上文）
- exec34478正常exit0。六正式report status completed，精确秒数：A短48.054031875/A长247.772215541/C短137.166507625/C长585.813914958/D短335.083100833/D长884.157396750。全部真实MPS+balanced。
- 启动controller/profile_runs.py，exec98108。A已完成一次真实profile（stats OFF），外层timings prep134.521762792/recog42.918070708/render10.061193209/total187.501026709。未启动C/D。
- A控制器期待TTY Recording但pipe真实ready=Ctrl-C to stop the recording，所以仅kill普通用户控制器38393，保留runner/samplers/worker并手动release，同一A未重跑、未第二次鉴权。进程快照profile-control-A/controller-recovery-processes.json，真实recording.json完整targetUID501/clockmap/命令。profile源码完全未变，只修docs/ai控制脚本ready判断与避免重复stop。
- A python flamegraph已保存17532 samples/0errors，inferno忽略1invalid-line警告保留。等待样本在图内，报告须聚焦recognize子树或明确等待，不把占比当纯PythonCPU。A普通worker38406/runner38396/auth38408均已退出；xctrace PID38407还在保存，日志显示Target app exited, ending recording / Stopping recording，CPU与RSS仍增长（13:51UTC age392s/CPU531s/RSS10367MiB）。等待明确Output file saved后再启动C/D，不早export。曾在目标exit自动ending后发送SIGINT；新控制脚本已避免重复stop。
- A trace已保存后，记录完成status；用修正脚本显式参数 C-short D-short 继续，不默认重跑A：caffeinate -i .venv/bin/python docs/ai/performance-baseline/controller/profile_runs.py C-short D-short。用户询问刚才是否osascript再次鉴权，已明确答复是，仅py-spy，本机APP普通用户，无权限配置改变；已有授权范围未变。
- Native分析脚本已准备650行流式id/ref，profile-analysis/input.md新补充识别窗口过滤（clock benchmark_start至rendering，用recording.monotonic_to_epoch_offset_s和TOC summary/start-date映射trace-relative），agent baseline_inventory正在仅更新脚本，不执行重任务。三trace完全保存后再授权运行。
- developer只读核实历史C2/D2：当前SHA与历史不同，D旧无音轨现有音轨；当前配置相同。旧报告model_inference=false（缓存观测），本轮真推理，旧观测缺失。不能从SHA差异断言像素因果已解释；也不能把不同输入/执行路径的历史数字视同本轮受控回归。当前用户批准的验收替代仍是三真实短片统计ON/OFF严格比较。最终报告不继承历史效果结论，保留具体区间差异与不可比边界；不新增已撤销旧缓存验收。
- 提交前注意controller/profiler/probe-toc.xml含完整environment，原始证据移到忽略runtime、docs/ai只保留去environment/设备私密ID的副本及原SHA引用，勿把环境凭证等提交Git。正式trace/导出TOC都在忽略runtime。

## 原生全程录制保存异常，等待用户覆盖决定（最新，覆盖旧状态）
- A1原生PID38407在worker结束后长时间不能完成save，trace约9GB，sample显示com.apple.dt.frame.activity/DVTInstrumentsAnalysisCore活动整理，工具CPU约940s/RSS11GB，当前host available28.8GiB/swap1.8GiB（非app基线资源）。尝试只读export toc明确exit10 Document Missing Template Error，因此不能作有效交付。已terminate该普通用户xctrace（非kill被测app），保留profile-control-A/native-unfinished.trace + failed-native-finalization.json + save-sample.txt + xctrace.log。原A1recording重命名recording-python-pass.json，Python有效SVG仍在原地。六正式不重复。
- 已实测更聚焦组合：Time Profiler模板 + GPU instrument + os_signpost，12s普通MPS probe PID41197（无root），正常save并export有效。app.runtime/focused-preflight/verified.json证实CPU594target/GPU3064target/PyTorchMPS18384，raw.trace和XML保留。
- A2仅原生补录（未再次py-spy、未root授权）：controller/native_recovery_A.py exec60506仍运行等save，普通worker42952/runner已完成，xctrace42953新native.trace约4.3GB，log native-focused.log仍Target app exited, ending recording，无Output saved。recording.json现在target_pid42952、native_case_directory app.runtime/profile-native-A/A-short、native_benchmark_clock_path其evidence/benchmark-clock.json；python_capture关联A1 PID38406/原SVG，不能伪称同进程。A2appreport app.runtime/native-A-report.json completed。A1/A2预测和export_ranges均与正式A短严格相等；全AV解码/实际帧数尚未检查。
- 原完整native两组合都长期保存，未成功交付A原生。主控已向用户async询问：改主要阶段5–10s原生窗口（A/C找球，D找球+CPU姿态，完整处理+Python采样照常，不能推算全段GPU利用率）推荐，或继续等待全程。答案尚未收到，不得擅自缩短原生覆盖；C/Dprofile暂未启动。可以继续整理不依赖该决定的六正式数据。
- 用户此前问是否又osascript鉴权，已说明是A1 pyspy本次附加用管理员，仅sampler，后端/模型普通用户，没改系统权限。A2及 focused probe没有任何管理员授权。
- controller/profile_runs.py已修pipe readiness为Ctrl-C to stop the recording，避免目标auto-ending后额外SIGINT；组合现在TimeProfiler+GPU+os_signpost，元数据native_case_directory/native_benchmark_clock_path/python_capture（target_pid/case_directory/flamegraph）已准备。但C/D未启动，若用户选窗口需再准备控制时序，不擅改源码。
- profile-analysis/native_profiles.py已由低成本agent更新明确native路径、不同Python捕获关联和识别时钟窗口，syntax通过，未execute。validation/validate_outputs.py更新10输出（6formal+3Python profile+1A原生补录），额外严格比A2与baseline，syntax通过，未execute。
- baseline_developer正在最新input允许下整理六正式JSON/CSV/曲线到app.runtime/report-preparation，仅读小证据，不改正式正文/README/路线图/源码。原生选择与数据有效性未解决，不能开始终验或提交。
- 原生A1失败具体因果未定：先前ready控制器bug导致等待，后来目标退出后额外SIGINT可能影响保存，采样显示活动数据整理；不要断言只有Metal模板是根因。A2无额外SIGINT仍长期整理，聚焦probe短时间成功。若用户同意短窗口，应先真实CNN短窗口验证save/三个表target非空，再将3类剖析运行完成；记录实际额外恢复执行次数，不伪称严格9次。

## 2026-10-21 恢复：原生短窗口已获用户确认
- 用户答复“按阶段短窗口（推荐）”。A完整原生已保存/解析通过，复用；C/D尚未开始，准备按真实stage触发8秒窗口（进入4秒后），Python整段保持。
- A解析成功summary app.runtime/profile-analysis/A/full-native-A-parse1/summary.json：目标42952，56.257估算累计CPU秒；Metal Active并集21.873s，PyTorchMPS170595事件，三表refs诊断0。Python原A目标38406，独立捕获，不混同。
- 原生CNN5秒工具探针实际TOC覆盖7.890086s，普通UID501，目标CPU4253/GPU2365/MPS28224，保存/导出/解析均有效。位于app.runtime/cnn-window-probe/verified.json。请求时长不等于TOC实际覆盖。
- 恢复前只读核对147个冻结实现文件SHA均无变化，剩余磁盘1491GiB，无残留xctrace/app.benchmark/app.worker/py-spy进程。
- 开发角色实施控制器；分析角色准备显式窗口解析；validation角色准备原SVG摘要。应用源码、六正式记录继续冻结。未启动新鉴权。

## C/D短窗口运行已启动
主控执行 profile_runs.py C-short D-short（exec session30703）。C普通UID501目标50312完成完整识别/成片与observation原生8秒请求，trace退出0且有Output saved；recording无诊断，等待TOC/目标样本正式解析。C原始predictions/export_ranges与baseline严格相等。C py-spy log记录22667 collected、2次相同线程展开失败警告，正常退出；保留原日志，不能写0错误或无缺口，后续摘要需报告缺失样本及限制，不据样本率推墙钟。
D已生成profile-ready，普通UID501目标51087，当前等待系统py-spy附加授权，未release。已在用户评论提前说明两次附加可能分别弹窗，并通知D实际等待。未重跑C或变更冻结源码。

## C/D已全部真实完成
exec30703正常exit0，C目标50312，D目标51087，均UID501，runner/pyspy返回0，控制记录无diagnostics。C observation与D observation/pose已正常保存（各请求8秒，实际TOC待解析）。已授权原生C/D顺序导出解析，PythonC/D摘要与10输出完整核对，以及开发角色正式报告写入；147个应用/算法冻结文件仍不得修改。正式六组没有重跑。

## 现行工具集中公共controller目录
最终原生C/D在phase-windows-final-v2，状态C/D observation passed_with_signpost_tail、Dpose passed；A full-native-A-parse1不变。窗口内有效证据与原始边界限制同时保留，不把工具表尾部加进分析。十输出与三短统计ON/OFF均通过实际核对，报告正在补全，独立验收未开始。
三个.py从profile-analysis/及validation/迁至controller/，不留重复入口：native_profiles.py、python_profiles.py、validate_outputs.py。ROOT父目录深度相同，不改内容。目的是让独立验收可读取公共实现而完全避开角色通信目录。旧角色通信和运行记录保留历史路径，当前入口/报告使用新路径。原生逐边界事件5.1MB已在app.runtime/profile-analysis中，不加入Git。


## 历史段数比较的事实与边界
此处从已完成的只读调查提取事实，供报告引用；角色通信不作为独立验收的读取入口。

- 旧C2文件SHA为 `7215d4acf604834d44a5073f8c9a504642322c7528d8077688db932ab8292d74`，当前恢复版为 `f270602edffd9c6b081cb0463de9aa97f6d1ef3027b0b16d86ab46941bb07f5c`。路径与字节不同，未据此证明像素不同或认定造成区间差异。
- 旧D2文件SHA为 `19d57eefda7817a5940c674468b16df9de9236eb91b522c1d45404d1794a67e8`，当前同名文件为 `360e3de1018a9656770ea432c903afba44cff29c0052f03ea65606a5200867fd`。帧数7527与窗口相同，旧音轨数0、当前1；不能据音轨/容器差异推断视频像素或具体因果。
- 历史 [C报告](../../../../modules/rally/experiments/reports/c-pause-boundaries-20261019.json) SHA `e2cecf480effd6ab1d5e686f227a52fea379ae02f2d38def84df529cf94d8310`，[D报告](../../../../modules/rally/experiments/reports/d-person-context-20261018.json) SHA `a19d5748f7f99a813fdf9003904799be5e337df8c24db7a3803bf5864efe97af`。两者model_inference=false，使用冻结观测；本轮当前产品入口是真实模型推理，旧35观测已缺失。已比较的选中C config、D candidate/base/options与现行profiles相等；历史court与设备未冻结，不能确认相同，也不能归因于它们。
- 旧C8段、D14段与本轮C9、D13段不同，具体因果未定位。该历史不是相同冻结输入与路径的受控比较，不继承旧准确率、不称旧回放通过。用户已明确批准三短真实统计ON/OFF替代旧缓存验收；本轮三对照和A额外对照已严格相等，不等同于证明历史效果一致。

## 最终交付准备
开发角色已停止写入，正式报告/33项小资产与当前入口完成。主控将人类报告两处开发通信链接改指本公共执行记录，避免独立验收读取开发通信。源/配置/算法147冻结文件未改；下一步冻结最终文件摘要后派全新独立验收。未提交、未推送、未合入。

## 第一轮独立验收已启动
冻结版本r1-20261021-final，402文件摘要 f17a09efbd093a4a3a303960d2d407495c1667e08d990138f83413ab42484edc。新独立上下文baseline_verifier仅获verifier/input，禁止读各角色通信，核对功能/代码/文档与原始受限证据。所有实现/报告/公共脚本冻结，其他角色已停止写入。主控只维护未纳入实现摘要的任务状态；原目录近期另有多项其他文档修改，均保留，主控仅更新自己认领行，原outputs不读写。未本地提交/推送/合入。

## 第一轮验收结束，第二轮修正开始
独立验收首尾402文件SHA相同，功能及原生边界通过，整体因一处P2不通过：Inferno省略小于总样本0.1%的窄帧，SVG可见父区间扣可见子区间只得可见残余；不能称精确self，聚合也不能保证完整函数上界，识别分母仅可见入口并集。已停止验收后才派低成本correction角色最小修正公共工具、原SVG派生摘要及报告/索引。正式六时钟、10输出、全部原始SVG/log/trace与147产品文件保持冻结；不补采、不鉴权、不重新推理。

## 第二轮修正完成并冻结
版本r2-20261021-svg-semantics，402文件树SHA 394e22e11d6dc9874d6d28728741b7169765c6d1eae32f9dce9582d40a912597。相对r1仅变化：apps/video-clipper/reports/performance-baseline.md, apps/video-clipper/reports/performance-baseline/evidence-index.json, apps/video-clipper/reports/performance-baseline/python-summary.json, docs/ai/performance-baseline/controller/python_profiles.py。产品147文件、原始SVG/log/trace/视频和正式计时未改；开发角色已停止写入，进入第二轮独立复验。

## 第二轮独立复验通过，状态收尾待核对
独立复验功能/代码/文档均通过，输出verifier/output-r2.md对应版本r2-20261021-svg-semantics，首尾402文件SHA 394e22e11d6dc9874d6d28728741b7169765c6d1eae32f9dce9582d40a912597。现仅同步报告、app README、任务分支路线图、证据索引的通过/待人工确认状态；收尾冻结SHA a51b0b39a0900a7f6e47a8496ec2a88c0e1b71a8f7c3eb62733f6bc1ee094665。主线仍进行中，尚未提交/推送/集成。请验收角色只读核对状态差异后再本地提交。

## 状态收尾独立核查通过
版本r2-20261021-accepted-closure，402文件首尾SHA a51b0b39a0900a7f6e47a8496ec2a88c0e1b71a8f7c3eb62733f6bc1ee094665。verifier/output-closure.md确认仅四状态文件改变、全部限制保留，允许按既有授权本地提交。所有实现与人类文档停止写入，低成本角色仅核对冻结/暂存任务文件并本地提交；禁止push/merge，保留worktree等待人工确认。提交SHA以Git HEAD及会话最终结果为准，避免在提交后改证据制造脏尾巴。


## 2026-10-21 用户确认后集成 develop
用户确认报告并授权集成后，性能基线已合入 develop。报告、任务工作树与原始有效测量证据保留，路线图保留已完成报告引用供后续对照；未推送，未运行新基线或优化。集成验证与提交信息记录于 [integration.md](../integration.md)。
