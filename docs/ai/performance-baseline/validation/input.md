# 机械输出核对准备，第一轮
读 ../task.md、根AGENTS及必要实现。禁止读取developer/verifier/media/continuity/replay通信目录。当前六正式测量正在执行，不能运行测试、解码、剖析、SHA大文件或CPU密集任务，也不得改实现、报告或输入。
你的机械任务：只在本validation目录写一个独立核对脚本和output.md，稍后主控再授权执行。脚本使用现有Python/PyAV/FFmpeg，不安装、不网络。仅syntax compile可现在运行。
证据路径：应用.runtime/performance-baseline/baseline/六case，以及profile-A/A-short、profile-C/C-short、profile-D/D-short（三profiles当前还没开始）。每组result.json/evidence/result.json/resources.jsonl/manifest.json；正式evidence/statistics.json，profile应无statistics.json。
执行时应检查9项status completed、device mps、balanced、非空predictions/export_ranges；区间和output_duration_ms一致、产品三阶段和等于总耗时（profile单列不当基线）；实际输出文件SHA符合runner记录；FFmpeg完整AV解码与PyAV视频逐帧计数/尺寸/PTS单调及音轨结构；六正式均有统计且MPS样本非空，所有资源进程树里后端/worker及FFmpeg覆盖、样本间隔/错误保留。不要给已知时间戳原点差异编造失败；输出duration如异常只记录数据待主控判断，不自定宽松验收阈值。
逐类严格比较正式短片stats ON与profile OFF的原始predictions、export_ranges、视频尺寸/codec/音轨/实际解码帧数。编码文件SHA本身无需两次相等（但各自应匹配归档SHA）。
脚本保存应用.runtime/performance-baseline/output-validation/检查JSON及FFmpeg解码日志，失败也保留诊断，非0退出，不自动重跑原测量/修改数据。原生trace数据检查另由主控处理，本脚本不展开trace。
现在只准备脚本，停止后回报。

## 主控脚本复核补充（仍仅准备）
1. range_duration_check 若worker output_duration_ms与sum_ranges_ms不一致，按float精度断言失败；不要仅记录。
2. 解码输出尺寸必须等于outer.state.video的width/height，不能只检查内部尺寸一致；保存container/video/audio实际duration，供后续判断，不自行设宽容阈值。
3. MPS至少有一条合法allocated_bytes>0的样本，否则不是有效MPS证据；其余采样缺口/错误完整保留。
4. 当前runner_pids_missing_from_samples读取了未定义audit字段，请实际计算runner_summary.pids减observed_pids并保存，或删除无效检查。
5. 现在仍不执行实测文件核对，只更新脚本并syntax compile。

## A原生补录输出追加（仍仅准备）
A首轮Python采样有效但全套Metal模板原生保存失败，保留诊断。主控普通用户只补录A原生一次，不再次root pyspy：app.runtime/profile-native-A/A-short，report app.runtime/native-A-report.json，kind=profile/stats OFF。原profile-A/A-short仍为三组统计开关对照之一，不覆盖其证据。
请GROUPS另加入profile-native-A/A-short统计关闭，完整验证共10输出；额外将该恢复输出与baseline/A-short的predictions/export_ranges/实际输出结构帧数严格比较（原A那组比较仍保留）。源/输入不变，必要的执行失败恢复，不把补录耗时作baseline，不声称只有9实际完整处理。仍只准备，不执行，等主控授权。

## Python火焰图摘要准备授权（2026-10-21）
现在仍不执行10输出全解码，C/D尚未开始。可新增本validation目录python_profiles.py仅解析已保存的py-spy原始SVG与log。先对A执行，C/D准备稍后。不要改原SVG/日志，不生成新HTML/视频查看器，不读其他角色通信，不改应用源码。
SVG实际结构为xmlns SVG内 id=frames 的svg，total_samples=17508，g含title，rect有inferno命名空间fg:x/fg:w整数样本跨度及y。A log记录17532 collected/0errors，而SVG总数17508，必须同时保留两个口径差异，不能假设相等/修改原图。SVG每个frame含filename:line和样本数，沿fg:x/w与y定位父子。报告recognize、observe、person_signals、TrackNet/Pose入口及具体Python循环/库调用的inclusive帧驻留，另外通过下一层直接子区间并集计算self驻留；同函数不同line/stack不可直接加inclusive重复计数，按区间并集可解释地聚合。针对整个捕获及recognize子树分别给分母，Python等待/原生调用驻留不等同纯Python CPU，不把samples/rate推墙钟或实际baseline比例。A handshake长等待要单列，识别子树之外不进入算法热点结论。
保存runtime/python-analysis/A/summary.json，原SVG/log的path/size/SHA、SVGtotal、logcollected/errors、recognize覆盖和前30帧、自身样本。任何不符实际SVG结构失败留诊断，不猜测兜底。命令参数显式--cases A/C/D，C/D未保存不要读取或称通过。先A实际解析并output追加结果，然后停止等待10输出验证授权。

### 主控核对实际源码后的摘要修正
A“没有等待栈帧”结论错误：SVG title确有 main (app/worker.py:52) (10,427 samples,59.56%)，冻结worker.py第52行就是time.sleep(.05)的profile握手等待。请用冻结实际文件/行号就地校验这一映射，在handshake_wait中列明10427驻留样本与其SVG占比；仍不能从样本量推等待墙钟。删除不实“SVG无等待帧”当前结论并在output留纠正记录，不改原SVG。完整等待墙钟应引benchmark-clock profile_ready→benchmark_start，不能用frame samples/rate。
Pose实际路径是modules/models/keypoint_rcnn.py（读此实际文件核对），当前pose_entries匹配modules/models/pose会漏掉D。改为实际路径/函数与精确observe/person_signals函数匹配，不用文件名模糊包含猜测；C/D尚未有数据。对A重解析并保留旧summary小型失败/更正诊断，再写新summary，验证等待映射10427与recognize4210互斥，最后停写。

## 10输出与C/D Python摘要实际执行授权（2026-10-21）
主控controller exec30703已退出0，C/D完整识别成片均completed。C/D runner/pyspy退出0，所有应用/采样已结束；现在授权依次执行python_profiles.py --cases C D 与 validate_outputs.py，全10输出真实解码/SHA/区间/资源/统计开关核对。不重跑模型或正式测量，不改既有证据/源码/标准。
C py-spy log为22667 collected/2errors（两次同线程无法展开栈），日志保留；D目前仅知退出0，自己读实际log，不猜errors。摘要必须报告warnings、SVG/log样本差异，errors>0不能写0或全程无缺失；错误属于采样器展开失败，不能自动解释为应用错误，也不可据样本率推墙钟。若数据不够判定必要热点/等价核对失败，非0并留具体诊断；不得自行加宽容差或重跑。
验证若遇脚本bug，先保留失败结果并报告，允许按真实数据修本validation脚本且明确修正诊断，不更改验收标准。输出/自身output标版本、完整10项及3+额外A对照结果、采样缺口/错误、视频时长差原始值，最后停写。

### C采样错误的证据有效性判定（不改变功能验收）
C原始log明确22667 collected、2次针对线程8411946624的get_stack_trace展开失败，进程正常退出且SVG已生成。用户要求有效Python数据，并没有要求采样器零错误；不能把任何非零errors自动等同整个数据无效，也不能抹去2次错误。请将工具已成功解析且recognize有效覆盖的情况分为status=passed_with_sampling_errors，errors/原warn文本单列sampling_errors或warnings；只有必要SVG结构/refs/recognize覆盖缺失等作为failed issues。同样保留SVG/log样本差异，不能用samples+errors硬算精确失败率或由rate推墙钟，因为各口径未证实同分母。工具未展开2次调用栈的底层原因尚未证实，明确局部采样缺失；建议结论只能依据有实际覆盖的数据及原生互证，不声称完整无缺失/纯Python占比。最终独立验收要审查这些证据是否足够支持报告。
这是去除解析工具自行加入的“非零errors整份失败”门槛，不把缺失数据改成已采样或放宽三短等价/必要热点有效标准。按此修正小型摘要并保留初始诊断，继续10输出验证；若recognize实际没有覆盖，仍failed报告，不自动重采样或鉴权。执行结果给主控核实。
