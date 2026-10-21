# 第一轮开发输入
先读../task.md、AGENTS/README/相关模块说明要求。只在任务worktree写实现/所属文档及自己的output.md，不读媒体/verifier通信，不提交推送合入。
实现最小完整benchmark runner、可选统计及合成测试。主控负责媒体与工具数秒预检，已批准索引见task。暂不启动9次完整真实视频运行，待主控派发；你可运行普通测试/合成小视频。使用原目录.venv/bin/python既有依赖，可在worktree .venv建指向它的链接，但不改原环境；cwd/PYTHONPATH确保导入本worktree。原短片/权重只读，产品模型cache复制到本worktree.runtime再用，原outputs不读写。
py-spy==0.4.2作为可选开发依赖，不进发行包。资源采样已有psutil7.2.2(ultralytics依赖)，直接使用需在适当开发extra声明。主控可在/private/tmp独立装py-spy，runner支持显式可执行路径。profile握手用明确事件，不凭进度文案。
交付output标明版本、修改、测试/等价证据、未验证项以及正式/剖析运行命令。报告先建协议/入口，真实数值等实跑后生成。
## 主控澄清：第一轮计时边界
“导入”只指用户上传/导入录像，不指Python模块import。正式6次必须直接沿用产品timings（准备包含worker启动、Python imports、权重校验及加载），不得另减模块导入或新增“净计时”替代完整墙钟。profile握手和等待只在3次独立剖析模式启用；剖析耗时清楚标记，不作为正式基线。正式模式不允许等待采样器。
主控已实测：py-spy0.4.2安装在/private/tmp/smash-performance-tools/bin/py-spy；普通用户附加失败，osascript的do shell script ... with administrator privileges实际3秒采样成功299samples/0errors，被测probe uid501。root仅采样器。Metal System Trace + --instrument 'Time Profiler' + --instrument os_signpost组合已实录并保存，CPU/GPU实际表导出正在确认。证据批准目录见task。runner提供profile-ready/release握手与明确record命令可由主控附加，不必写常驻root helper。

## 回放输入授权澄清
cases.json 明确引用的 /Users/bytedance/workspace/test/meterials/outputs/realtime-input-20261005/offline/01-02-clip/tracknet-points.jsonl 已批准只读并校验SHA；它不是需保护的原仓库outputs目录。缺失的 C1 观测由主控核对恢复映射，不自行伪造或改期望结果。

## 第一轮数据缺口事实（未改变验收标准）
replay角色已按cases清单只读盘点：原modules/rally/.runtime及35个保存观测均缺失，限定outputs/无同名或SHA副本，原绝对A2观测路径也不存在。不要继续复制/猜测重建、不要修改回放期望。已向用户询问以三短真实输入统计开关对照替代的方案，答案未到前此替代未授权；其余实现/六次正式测量准备继续。主控会在收到回答后更新task。

# 第一轮补充开发输入（用户后续确认）
先读task.md新增“用户后续确认”。当前版本见你上次output与version.json，尚未开始真实9次测量。继续本worktree开发，其他角色通信仍不可读。
1. runner增加明确“关闭聚合统计”选项，仅允许profile模式使用，默认正式6次仍开启统计。内部benchmark config给worker传statistics_enabled；关闭时保留ready/release和MPS signposts，不生成假统计。公开HTTP请求/JobState不变。让3次profile可与正式短片真实输出做统计开关对照，保持总9次。补充必要的开关编排测试和命令文档。
2. 按用户清理要求删除旧检查独占的 modules/rally/experiments/cases.json 与 replay.py、pyproject该包data项；两者仅服务缺失的35份历史缓存，无其他运行依赖。同步 modules/rally/README.md、experiments/README.md、datasets/test-videos.md 的现用入口/说明，去掉失效命令与默认保留观测的当前声明。algorithm-decisions历史报告只需修正当前指向缺失.runtime结果的链接和当前验证入口，保留历史数值与决定。不要删除rally_stream.replay_frames或现有合成tests（同名replay并非旧缓存工具），不扩展为全库归档清理。
3. 完整pytest与diffcheck，更新你自己的output.md(保留先前交付历史并追加补充结果)、version.json，列出清理范围和开关方式。旧16回放明确记录被用户批准替代，不再当当前验收阻塞，也不称它通过。
4. 先不启动正式/剖析真实运行，补充完成后再次停止代码写入并回报，主控随后冻结统一版本测量。主控已准备权重在app .runtime/performance-baseline/prepared-models，可用于命令文档。媒体仍在完成像素/PTS与连续性检查，索引路径不变。

## 同轮报告准备阶段（实现继续冻结）
主控已开始六正式测量，前5组完成，D-long正在执行。实现SHA仍b0dd82c61618c5b4b2f59a8011b0d43710e5383a9d811ccd1847ef40d0681adf，任何源码/配置/README/正式报告改动均暂禁，避免九次期间变动。
本阶段只读已完成的 app .runtime/performance-baseline/baseline/{A-short,A-long,C-short,C-long,D-short}/ 的 result.json、evidence/{result,statistics,benchmark-clock}.json、resources.jsonl，以及既有实现。不要读取D-long活动资源、视频/权重大文件/trace，不跑测试/解码/导出/绘图等CPU重任务。不要读其他角色通信目录。
请先在自身output.md追加最终报告的分析提纲与5组证据初步判断（不是正式交付），并列出等待三短剖析才能确认的疑点。现在只写自己的output，不改正式文档/源码。
主控已核实：D短total335.1s，pose_inference_s162.0（包含PoseEstimator入口预处理/forward/回传，不可等同纯C++内核）；第二遍pose_decode_s7.61/pose_conversion_s6.42；action_analysis181.99互斥主阶段。C长total585.8s，people_and_trajectories20.83、video_observation491.40。子项嵌套，不能与主阶段相加。MPS样本只覆盖recognize上下文，非整个render生命周期。帧数/容器时长/归一化PTS和原始stream PTS在固定输入清单分开保留。
最终交付依旧必须等六正式与三有效剖析完成、九输出检查通过后，再获主控授权更新报告/资源曲线/小证据索引/应用入口/路线图。实现九次期间不变；正式report内容和生成结果文件导致全树SHA不同，应核对共同实现文件SHA一致而非声称所有manifest全树hash相同。

### 初步结果疑点补充
已收到C短9段/D短13段与历史报告C2=8/D2=14不同。请利用必要的现行正式算法报告、数据清单及小型参数清单只读核对两者具体输入SHA/窗口、配置/court、实现路径是否相同；不读其他角色通信、不读原outputs/、不把backup源码作当前证据，不跑模型/解码。只列核实到的差异，不猜测court或版本差异已解释。若原因仍未知，明确记录待验收前核实，不直接套用历史效果结论，也不能以统计开关未来相等就替代这项疑点调查。当前实现/正式文档仍不改。

## 六正式已齐：独立数据整理阶段（第一轮，仍不动源码/正式正文）
六正式已完整成功，精确数据以 app .runtime/performance-baseline/baseline/results.json 为准。允许读取全部六组已完成的小型JSON/逐秒资源/manifest，不解码视频、不跑模型/测试、不读其他角色通信。现在没有被测应用在运行，只有Instruments后处理。
请在应用.runtime/performance-baseline/report-preparation/生成六正式摘要JSON/CSV和资源曲线（可使用已有matplotlib，不安装）；自身output追加结论和图表入口。正式报告正文/README/路线图/源码继续不写，直到全部有效剖析与输出核对完成。
图表与摘要应清楚标CPU%单核口径、RSS合计可能重复共享页、MPS allocated/driver独立不与RSS相加、MPS只覆盖recognize、每秒观测峰值非精确峰值；保存实际采样间隔最大值与缺口，MPS与外部采样分开。CPU/RSS/目录/磁盘数据按product clock对齐，标准备/识别/成片边界；system_profiler等实际采到的后代保留计入。解码/模型子项嵌套并行不与primary相加。
本阶段只整理固定六正式，不能用profiles耗时作baseline。A/C/D短长来源不同，不证明复杂度或稳定性。输入容器duration与state.video.duration（产品使用的视频stream时长）分列，fps与PTS原点不混淆。
新进展：A首轮Python有效17532样本0error，原生完整trace约9GB后处理长时间不能正常保存，恢复export报Document Missing Template Error，已留诊断停止；普通用户A原生补录用验证过的Time Profiler+GPU+os_signpost，新trace约4GB还在保存。C/D未剖析。主控已向用户提出原生按阶段5–10s窗口vs继续全程等待的选择，答案未到；不得自行变更覆盖/声称完成。原生A补录额外一次full流程（无第二次root），最终执行计数应诚实，六正式仍各一次。
历史效果对比：核对已完成，旧输入SHA/音轨/缓存路径与当前不一致，因果未证实不伪称已解释；本轮不继承旧效果数字，也不把不可比的旧历史作为新的强制验收。用户已批准以三真实短片统计ON/OFF替代缺失旧缓存，这个标准不回退。保留已核实差异和不可比边界即可，不继续扩大历史恢复任务。

## 短窗口控制器实施授权（2026-10-21，第一轮）
先读task最新用户授权。仅修改docs/ai/performance-baseline/controller/控制脚本，应用源码/算法/既有六正式证据冻结，正式报告仍待全部数据。不要读其他角色通信。
将profile_runs.py改为只允许显式C-short/D-short，保留A历史控制证据。C/D完整app.benchmark真实流程与py-spy全程100Hz stats OFF。原生不再启动全程，C在“正在寻找羽毛球和球员”，D在相同找球以及“正在分析球员动作”阶段各录8秒 Time Profiler + GPU + os_signpost，进入实际阶段后等待4秒，再确认当前stage仍相同才附加。D CPU姿态窗口GPU/MPS为空可真实记录，不冒充全程。
不改变app.benchmark源码：在本控制器增加一个runner子模式，导入app.benchmark，包装其request函数，原调用返回后仅将GET且结果含status/stage的真实状态连同monotonic写controls/stage-current.json，并在阶段变化时追加stage-events.jsonl，然后benchmark.main(argv)。只观测现有状态，公开接口不改，不手写重复产品runner。controller根据该文件判断阶段。记录窗口启动请求、附加ready和结束单调时刻、阶段观测，trace自身TOC实际覆盖才是采样窗口，阶段变化必须报诊断。每窗口trace.wait可后台进行，避免影响runner/下一阶段；顺序启动，不同时录两个trace。py-spy先握手ready再release正常worker，不需要为了native等待整段。
recording.json保留target_pid/target_uid/native_case_directory/native_benchmark_clock_path/python_capture/monotonic_to_epoch_offset_s/release时刻/runner、pyspy退出码。新增native_windows=[{name:'observation'或'pose',stage,trace_path,trace_command,requested_duration_s:8,trigger_observed_monotonic_s,attach_requested_monotonic_s,ready_monotonic_s,completed_monotonic_s,trace_returncode,...}]。目录profile-control-C或D；trace分别observation.trace/pose.trace，日志各自独立。required stages未观察、process退出、保存失败等须非0且留诊断；清理只本次普通UID应用子树，不能广泛杀进程。不要启动/鉴权/运行真实模型，先syntax+控制逻辑核查，output.md追加变更和明确运行命令后停写回报。

### 阶段证据与解析端最终约定
recording.json须明确 stage_events_path 与 stage_current_path 绝对路径。stage-events.jsonl每条 {monotonic_s:number,status:string,stage:string,progress:number} 仅阶段或status变化时追加，stage-current.json每次GET原子更新同结构。不得存session token/请求headers。解析器将以此证明trace实际覆盖选定阶段；窗口跨阶段要报诊断。

## 最终报告任务预告（等待主控另行放行，目前不实施）
C已完成，D正剖析；你的控制器已交付停写。等全部剖析/输出验证有效后，主控会给明确最终数据路径并授权正式文档。本节仅提前固定交付要求，当前不要写报告或图表。
正式报告归apps/video-clipper/reports/performance-baseline.md，包含可复跑入口、固定输入清单JSON、六正式结果/CSV/耗时图与六资源曲线、三类PythonSVG与native有效数据的精简索引和可查看图表、优化优先级。原始trace/逐秒资源/视频/大XML保留app.runtime，并用文件树SHA和绝对路径索引关联，不放Git。小SVG/PNG和摘要归报告asset子目录，避免重复原始内容的大副本。
正文必须按读者要完成的任务结构化、中文标题与短段落：先结论/完整六结果，再瓶颈/可采取措施及限制，复跑和精确口径靠后。每方向列证据、耗时或资源占比、可能措施、隔离理想收益上限、验证方法；分实测支持/待验证假设，不相加嵌套或并行子项，不用profile耗时作正式时间。不仅列“优化模型”空泛建议。D姿态入口与重复解码分开，C关联上界只取该互斥主阶段，模型初始化/前处理/传输/内存积累/中间写盘/成片分别核实。内存不能由不同来源短长或RSS+MPS证明泄漏/容量总和。
C++/Rust：明确py-spy即使未来迁移仍可定位Python调用路径和边界，但macOS看不到内部native栈，Python self也会含原生调用等待，不等同纯解释器开销。结合实际native CPU栈与Python完整识别子树分析，只对已证实Python热点评价小范围迁移；没有证据不能声称整段重写提速。现有PyTorch/FFmpeg/OpenCV已有原生计算，不因改语言自动更快；C++/Rust调用边界、额外拷贝、维护成本要列出。官方基础来源可直接链接 https://docs.pytorch.org/tutorials/advanced/cpp_frontend.html 与 https://github.com/benfred/py-spy#can-py-spy-profile-native-extensions ，主控2026-10-21已核对原文支持这些一般说明；不把其文档最新版本当本地依赖。
A Python与native两次不同PID必须明确，A全native复用，C/D为实际短窗口（请求8秒，TOC实际时长另外列），Dpose允许GPU/MPS为空且结合源码CPU路径；不能由窗口外推整段利用率。A长握手等待基于clock单列，不能把wait帧当算法热点；SVG accepted与log collected差异、C采样2次展开失败（若D也有）都保留，不写全覆盖或0errors。实际完整产品执行10次：6正式+3Python剖析+A原生补录；不继续沿用恰好9次旧说法。
初始旧A native保存失败、解析脚本修复/重复导出partial等执行细节放docs/ai，正式正文只保留必要测量限制/恢复说明并链接，不堆调试历史。旧16缓存检查由用户批准三短真实ON/OFF替代，历史C/D不同SHA不可比原因未证明，不继承旧准确率，也不扩成当前强制验收。单次6输入不推波动/复杂度，不替代30分钟产品验收。
同步app README入口与任务WT路线图状态/证据；正式报告不得声称独立验收已通过，待主控独立验收。主线develop仍进行中不动本任务以外条目。文档/证据最终完成后输出所有文件和执行检查，停止写入，等待主控冻结验收。

## 最终正式报告实施放行（2026-10-21）
主控实际C/D控制器已完整退出0，三trace正常保存，无diagnostics，三类PythonSVG均生成。6正式+3Python完整处理+A原生补录10输出已齐。现在解除“正式正文/README/路线图不可写”限制，仅应用/算法/测试/配置源码仍冻结147文件不变。按上一节完整交付要求实施正式报告及必要图表/小摘要、固定输入清单、app README与WT路线图，不动原目录/提交/推送。
公共最终数据路径：六正式 report-preparation/six-formal-summary.{json,csv}及六PNG；A原生profile-analysis/A/full-native-A-parse1/{summary,artifact-index}.json；C/D原生将由已授权分析角色生成profile-analysis/{C,D}/phase-windows-v1/{observation,pose}/summary.json与artifact-index.json（C仅observation，D两项），使用前等文件存在且status passed。Python summaries python-analysis/{A,C,D}/summary.json（A已纠正等待10427样本映射worker52，recognize4210；C/D正在生成）。10输出验证output-validation/最新run/validation.json正在生成，使用前读真实结构/状态并核对所有10项/对照均通过，未齐时不得声称检查通过，等待主控后续通知即可。不要读分析/validation角色通信，只读这些公共runtime及你的输入/输出。
可先复制六正式资源图/耗时图、固定输入manifest并整理正文，然后等实际原生/Python/验证数据齐备补完。若任一数据failed请向主控报告，不替换数值/猜测或自行修应用，不把启动当验收完成。独立验收尚未启动，报告不写已独立验收通过；WT路线图暂记进行中/实测完成待独立验收，完成状态由主控验收后调整。原主目录路线图保持进行中与认领。
小摘要/资源图/SVG拷入reports/performance-baseline/，将runtime大证据SHA与路径索引关联。可生成原生各窗CPU热点柱图/Metal区间时间线（目标PID筛选、标实际短窗口，A全程与C/D窗口区别），不要自行生成视频标注查看器。报告内点击原始.trace可用Instruments查看；无必要二次复制raw/XML，A已成功hash索引用公共artifact-index引用。
主控已网页核对官方PyTorch与py-spy文档支持一般语言边界说明，最终正文来源直接链接即可，不写依赖新版已安装。按需要做文档链接/JSON数值/图表可读性/冻结147文件SHA和git diff --check，当前不必再次全产品测试（独立验收会重跑）。完成后自身output列出文件、证据、验证与局限并停写。

### C Python采样局部缺失的呈现
主控已核实C两条get_stack_trace失败/22667 collected，正常退出且SVG生成。原用户标准是有效数据，并非采样器零错误；validation工具的任何errors即failed为自行加入门槛，已要求修正为有必要识别覆盖且能解析时status=passed_with_sampling_errors，保留2次错误与具体warning，不抹去局部缺失。请将这个明确受限状态作为可引用的局部采样证据，正文必须说明展开失败2次、底层原因未证实，不由samples/rate推墙钟/失败时长，不称完整无缺失。结论需有实际recognize覆盖及native互证；独立验收最终判断证据是否足够，不声称三份均零错误。若结构/必要覆盖不足仍failed不能引用为有效，遇此报告主控。继续其他报告工作，不需启动额外采样/授权。

### 主控已核实的输出/Python最终公共数据
10输出成功核对：app.runtime/output-validation/run-20261021T024238Z/validation.json，status passed，actual/expected10，issues空，A/C/D原三对照及A原生补录额外对照predictions/export_ranges/output_structure均严格相等；每输出range_duration delta0。先前run-20261021T024200Z是调用了错误解释器缺av导致的环境失败，保留诊断，不作为数据失败或当前结论。实际有效运行使用本仓库既有venv，无安装/改依赖。
Python A status passed（SVG17508/log17532/errors0），C passed_with_sampling_errors（SVG22631/log22667/errors2），D passed（SVG46137/log46153/errors0）；recognize子树并集样本分别4210/12179/32199。C observe11540/recognize12179；D person_signals17982、Pose入口16058/recognize32199，属于inclusive栈驻留，不可当正式墙钟或纯PythonCPU占比。A握手睡眠10427样本单列与recognize无重叠。以上路径python-analysis/{A,C,D}/summary.json已真实生成，可读取。
原生C/D首版phase-windows-v1解析failed是工具校验/脚本问题，正在保留失败并复用成功XML核实尾部标记边界，后续成功目录预计phase-windows-parse1，必须等待主控确认有效后使用，不用failed数值写成结论。六正式/App源码无变化。
主控已清理A未完成不可导出trace约9.7GB和重复partial导出约128MB：先保存全部原文件SHA与大小清单app.runtime/profile-control-A/cleanup-inventory.json，再删除这两个无效中间目录；controller/cleanup.json是小型执行索引。有效A/C/D原始trace、三SVG、失败日志和原生A补录数据均保留。正文无需堆清理详情，执行记录链接即可。

### 主控正文复核：时长与语言判断措辞
当前第26行“每份成片时长与导出区间求和之差为0”需精确为“worker声明的output_duration_ms与导出区间和差0”。实际输出容器/视频stream时长是另一个口径：A短容器46.44s、视频stream.duration46.42s、首视频PTS0.02s、末PTS46.42s；A长同样stream.duration比容器短0.02s，起点0.02s。这与保留真实帧间隔/共同音画起点的实现相符（模块render select后保留实际首帧偏移；stream start+duration才是末端），不是把声明时长当逐帧视频覆盖。请明确分列或用一短句解释A的20ms首帧偏移，保留actual container/stream/first PTS，不把range_duration_check的0当媒体所有时长都0差。
语言节当前“再对C候选小循环等明确热点做微型原型”容易把inclusive调用驻留认作已证明解释器瓶颈。请改条件式：先用更窄的CPU计时/原生栈确认具体Python循环/对象处理开销，再对该小段做C++/Rust等价原型；C当前整个主阶段仅3.6%上界且含NumPy/SciPy原生调用，不能凭火焰图断言纯Python占满。明确本轮没有证据支持全模块语言迁移，C++与现有PyTorch/OpenCV接口较直接、Rust需评估绑定/数组所有权成本，无本轮证据证明二者谁更快。仅作为下一轮条件建议，不实现新优化。

## 原生最终有效数据已由主控复核，可补全并交付
最终公共目录为 app.runtime/profile-analysis/{C,D}/phase-windows-final-v2/，C observation、D observation/pose，均有summary.json/artifact-index.json；不要引用旧parse1/parse2/failed版本。C/D observation的状态是passed_with_signpost_tail（errors空），Dpose passed；A仍full-native-A-parse1。CPU原点校验现读完整raw范围，CPU/GPU严格在TOC内；三个stage都匹配，refs/duplicates0。主控读取指标：
C observation实际主窗trace-relative[5.095072746,13.045599937]跨度7.950527s，CPU10411样本/10.411估算累计秒，Metal Active并集4.634414s，MPS65855事件/裁剪配对interval union5.652257s；D observation[1.245430231,9.189937115]跨度7.944507s，CPU9559/9.559s，Metal2.661880s，MPS49367/裁剪union3.538855s；Dpose[1.043334246,8.956340075]跨度7.913006s，CPU10245/10.245s，目标Metal/MPS为0（源码CPU路径）。TOC完整原始跨度分别13.0456/9.189937/8.95634s，包括就绪前工具附加，主统计取已记录ready→TOC结束∩recognition，ready是0.1s轮询观察值，不按热点挑选时段。不能把TOC13s写成8s，两个范围都标清。
Signpost表实际完整尾部超出TOC C0.559535s/D0.549400s，包含Begin/Event/End及MPSGraph，不能用“仅End异步完成”解释。主控用先行独立CNN5s工具探针复核也复现0.568773s尾部（TOC7.890086，目标signpost最晚8.458859），见app.runtime/cnn-window-probe/stop-boundary-check.json。这表明导出表覆盖范围可超出run摘要，当前处理保留并排除尾部，未改offset/容差；xctrace内部缓冲/停止机制未证实，不声称无异常或已证明具体根因。CPU/GPU严格原点、有效目标样本、正确stage、refs0及窗口内MPS均独立成立，所以作为带明确覆盖限制的短窗口证据，最终由独立验收审查是否足以支持报告结论。
原始边界事件清单已移到app.runtime/profile-analysis/signpost-boundary-events.json（5.1MB，原字节SHA不变），final-v2 summary/index都指新位置；不要把整份逐事件表复制Git/人类正文。报告精简摘要保留状态/范围/计数/诊断与raw清单SHA路径即可。MPS interval union是标记驻留窗口，与Metal GPU时间不同，不能比较二者就推利用率或kernel时延。
现在补全native章节/图表/索引（主统计使用新7.9s窗，A full独立），检查全部当前链接/来源SHA、147冻结、git diff --check，再输出完整交付并停止所有写入。不要声明已独立验收通过；主控随后冻结最终版本并派独立验收。

### 独立验收前公共工具位置已整理，更新当前引用即可
主控已将三个.py（内容未改、目录深度未变）移到 docs/ai/performance-baseline/controller/：native_profiles.py、python_profiles.py、validate_outputs.py，旧profile-analysis/和validation/位置不留重复入口。角色通信目录现在只放输入/输出，使验收可读实际实现又不读对方通信。请将本次人类报告及当前README中涉及这些脚本的链接/命令更新到controller新路径；历史执行记录不改写，只作迁移说明。ROOT计算仍正确，原始数据路径和final-v2指标不变。CLI --help与实际输出检查将由主控/独立验收在新入口验证。不要再从旧位置读源码或恢复副本。
