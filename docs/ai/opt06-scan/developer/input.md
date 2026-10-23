# 第1轮开发输入

唯一worktree /Users/bytedance/.codex/worktrees/opt06-scan/smash-suite，codex/opt06-scan，起点94a8465。先读task.md、根AGENTS/README、modules/media/README、modules/models/tracknet/README及必要实现；不要读verifier目录。

只实现docs/ai/opt06-scan/scan.py及test_scan.py（定向检查）。不要写modules/apps产品代码、改配置/依赖/原分析、不运行真实视频或模型。报告待主控得到结果后另交接，暂不写猜测结论。保持脚本尽量小，不复制07A的大型验证框架，不做候选/回退兼容或无必要抽象。

CLI固定：--inputs <manifest>、--case A-short|C-short|D-short、--models <existing models dir>、--reference <normalized reference.json>、--output <new directory>。主控会准备参照JSON：case_id、video_sha256、predictions（含start_ms/end_ms）、export_ranges（二维起止列表）、provenance（供原样记录）。严格检查SHA匹配，不自动猜参照来源。

运行脚本须将项目root放sys.path前面，核对当前工作目录与实际模型/输入模块来源在本worktree；不从主目录误导入。验证manifest该case passed、实际媒体sha和ball_track.pt的ASSETS大小/SHA，无缓存时失败，不调用ensure下载；没有MPS时失败，禁止CPU替代。用实际TrackNetPredictor显式weight、MPS，record_candidates=False，confidence为heatmap max，三帧一组且不启缓存。统计复用Statistics/last_timing即可，不另造模型包装。

按FileFrameSource完整EOF迭代，每整数源秒首三帧（floor(timestamp_ms/1000)，FileFrameSource已首PTS归零）。每组保留原frame_id和时间，不重编号/合成；当前>=25fps，桶内三帧连续。不完整末桶记录其原frame_id/时间但不推理；读取全片时最多保留当前3帧，不能list整视频。保存所有组的每帧confidence及秒号和positive标志。请将采样与区间覆盖逻辑做成两个小函数，便于针对真实错误边界做少量检查，避免测试照抄实现。

覆盖按每个采样帧时间处于[start_ms,end_ms)且confidence>=0.5计算，不以秒桶或组范围重叠算命中。分别报告predictions和export_ranges，每段含index/start/end、采样数、阈值命中数/是否命中、最大分数与命中时间，允许没有采样时max为null；阈值包含0.5。不要把返回坐标当global_peak位置，不需要保存坐标。

输出至少report.json：status completed、case/input/ref/code/weight SHA及路径、配置/环境/device/thread实值、groups、incomplete_tail、source stats、raw/export coverage、统计与计时。保存stats原始计数（TrackNet calls/input frames等），model_setup_s与scan_wall_s分开，outer wall说明是否含输入SHA/导入/写盘；分项不相加宣称总成本。可以记录自身resource.ru_maxrss（本机mac字节）但不必新增采样线程；成本单次观察不称稳定提速。异常须保存失败状态/错误再抛出，不把半程算完成。当前三片帧数/容器期望完整性由FileFrameSource保证，同时检查frames_delivered==frames_decoded及预期非零帧数。输出目录必须新建，禁止覆盖旧证据。

测试只跑test_scan.py的有意义定向检查，导入时不得启动模型/下载。测试命令本机pnpm无关，直接.venv/bin/python -m pytest docs/ai/opt06-scan/test_scan.py -p no:cacheprovider。git diff --check。完成写自己的output.md，标本轮、实际SHA、已执行与未执行，然后暂停，主控串行真实模型，验收另做。

## 第1轮边界补记

每秒桶的采样组只用于定位，不能代表一整秒候选区间；覆盖逐帧使用timestamp和score。末桶partial记录但不推理，completed只能在完整EOF后写。固定输入按既有PTS预期A168、C180、D251组，仅作结果核对提示，不在实现中硬编码，仍以本轮实际PTS为准。主控目前无模型活动，允许定向测试。

## 第1轮主控检查后的最小补齐

生产模型尚未运行，仍属本轮开发收尾。现有采样与逐帧覆盖逻辑符合方案，请只补齐以下已约定证据字段，不扩展实现：

1. report中保存实际worktree绝对路径、git HEAD，以及已通过路径校验的FileFrameSource/TrackNetPredictor/TrackNet的真实__file__路径（现在code只记录相对路径SHA，缺少实际导入路径与版本）。保留现有本worktree路径校验，Git只执行只读rev-parse。
2. 每段coverage补充完整hit_timestamps_ms，直接来自当前hits。既有边界测试同步期望，另核对有采样但全低于阈值的区间（应hit false但max仍有数值）和仅扩展后的范围命中的情况，不能把低分/无采样混为一种。请保持测试少量而明确，不新建框架。

只修改scan.py/test_scan.py及自己的output，重新跑这两个检查与diff check，记录新SHA后暂停。不运行模型或视频。

## 第2阶段：仅计算候选区间，不运行模型

用户已授权后续确定/高优先级任务无需再次确认。第1阶段三个真实扫描已完成，报告在apps/video-clipper/.runtime/opt06-scan/{A-short,C-short,D-short}/report.json。原scan.py/test_scan.py保持冻结，不改产品代码或已有报告。

请新增docs/ai/opt06-scan/candidate_windows.py，复用保存的逐帧正例计算扩展候选，输出apps/video-clipper/reports/opt06-scan/candidate-coverage.json，并把三个原始scan report逐字节复制到该报告目录，名称A-short.json/C-short.json/D-short.json，保留源SHA。无新推理/视频解码/测试模型。实际视频时长/播放偏移用modules.media.video.probe从现有原片元数据取得；不要用原始回合emitted_at猜视频时长或按帧率伪造时间。

候选定义：每个confidence>=0.5的采样帧是一个源时间点，向两侧分别扩展1000/2000/3000/5000ms，裁到[0,duration_ms]并合并相交或相接区间。参数按同一表用于全部case，不用当前保留区间作为运行时oracle来补洞或调整每条边界。分别记录合并后的候选区间、总保留时长/比例、可跳过源时长、原始预测各段和导出区间各段完全被候选覆盖与否，以及每段未覆盖的具体子区间。必须区分“有命中”与“完整区间被覆盖”，不能把间隔中的低分点当真负例，也不能称算法准确率。

可记录原始粗查成本、正例帧/组数量以说明前置开销；不把保留时长比例等同完整耗时节省。这个计算只用于选择后续必要的真实候选分析试验，不宣称已经实际跳过或完成OPT06。输出包含输入扫描report SHA、当前脚本SHA、元数据来源、候选规则。命令入口可固定读取本任务三份已保存report，允许--output显式新路径但禁止覆盖旧证据；不要引入一般化配置或依赖。

添加少量真正检查合并、边界裁剪、覆盖间隙的定向检查到原test_scan.py或单独test_candidate_windows.py（推荐单独，保持第一阶段文件SHA不变）。运行定向检查及diff check，记录自己的output并暂停。主控同时在做轻量源路径审计，无模型活动，可执行这组小检查。不要写人类报告结论，待主控按数据决策。

## 第3阶段：A 候选成本下限试验入口（不改产品）

候选几何已显示：C扩展2秒后保留100%，D要扩展5秒才完整覆盖原始/导出区间、保留99.6%；A扩展3秒能完整覆盖两类区间，但保留约61%。这几项不能直接按保留比例宣称提速。先测A一个乐观成本下限：完整读取同一源视频，在原生合法三帧窗口上，只对候选窗口调用TrackNet，省略全部回合判定。它不是recognize输出，不伪造未观测球点，不是实际产品跳过；如果此成本加前置粗查已不优于完整原版，就没有必要引入当前入口的跨区间状态改造。

请仅新增 docs/ai/opt06-scan/replay_tracknet.py；不要改phase1/2文件或任何modules/apps。CLI --variant full|candidate、--inputs、--models、--output（新目录）；case固定A-short，candidate固定使用candidate-coverage.json的3000ms统一扩展结果，不读原始保留区间作oracle。main复用scan.py的ROOT/sha256 helpers，确保真实模块来自本worktree、MPS可用，验证媒体与ball权重SHA，不下载。不新增通用参数或框架。

完整FileFrameSource到EOF，每连续原生frame_id三张组（起始0、3、6...），两种variant都维护同一完整分组。candidate仅在组内任一真实时间点位于候选[start,end)时调用当前TrackNetPredictor；一旦调用必须传原三张相邻BGR图像。其他组不调用模型、不生成球点或影响源帧编号，末尾不足3只记录。frames_decoded/frames_delivered必须与容器相符；保存实际源帧数、总/执行/跳过窗口数、所有执行窗口起始ID和候选规则/源JSON SHA。full对所有原生三帧组调用模型。预测结果无需保存，只核调用返回三点。

计时仅模型setup与完整replay墙钟，Statistics保存TrackNet分项/调用计数、source stats和MPS内存；元数据记录输入/权重/源码SHA、实际import路径、git HEAD、device/线程实值。输出report.json completed必须在完整EOF后写，失败写error。说明这是省略分段/选人等下游的乐观成本测量，不提供回合/准确率结论；嵌套分项不能相加当墙钟。模型运行由主控串行执行，你只完成脚本和必要的组门控定向检查（小函数验证半开边界、组内任意帧命中且分组不拼接），跑小检查和diff check，更新output后暂停。

## 第1轮最终报告与收口（主控决策，2026-10-22）

第3阶段主控已串行执行full与candidate，完整报告在apps/video-clipper/.runtime/opt06-scan/replay/{full,candidate}/report.json。请只读真实JSON而非转录：full1400窗/29.529457959s，candidate859窗/23.273038125s，两者完整4200帧。A scan18.093526083s；其和41.366564208s仅为省略下游/共享复用的分阶段乐观观测，非产品总成本，不是严格数学下限，不能宣称全方向绝无收益。当前完整A原版35.655s来源参照镜像需取精确值。单次、不稳定收益证明。

主控决策：本轮指定粗查+固定扩展候选不采用，不改产品。C1s已保留99.44%；D需5s保留99.60%才覆盖所有当前raw/export；A3s保留60.98%，但粗查+候选TrackNet回放已无成本优势。实际跳过会引入状态/人物/第二遍解码的语义变化，现证据不支持付出该复杂度。本轮高优先级尝试以“诊断完成，当前候选不采用”收口；更细动态扩展、真实跳过和泛化效果仍未验证，不宣称整个粗筛方向无效或已完成产品功能。用户已授权主控自动取舍，无需再次确认。

请完成：
1. 将full/candidate原报告逐字节复制至正式reports/opt06-scan/replay-full.json和replay-candidate.json，核对SHA。
2. 写简洁人类报告apps/video-clipper/reports/opt06-scan/README.md：先结论/适用边界，再三片命中与成本、1/2/3/5秒几何覆盖重点及缺口、A成本回放；所有来源与原始JSON链接；当前94a8465原版，不把07A收益混入。27条都有至少一个命中仅覆盖诊断，不是逐段全覆盖或准确率；raw/export与人工真值分开。无匹配标注，不需要添加viewer或伪人工行。
3. 更新本任务task.md当前状态与完成标准7，仅按新授权明确诊断/当前候选取舍完成，动态细查/真实跳过未实施；修正过期“仍等用户合入07A”文字，注明07A已独立集成4910e1e，本轮版本不变。不要写其它任务的认领/完成状态。
4. 把developer/output.md末尾过期“当前只新增scan”状态改准确，保留已发生记录，不重复模型/视频运行；运行6项定向测试与diff检查。不要更改任何生产代码或既有实验入口与JSON。完成后暂停，等待冻结独立验收，不暂存提交。
