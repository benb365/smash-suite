# 开发第1轮共同约束
工作目录 /Users/bytedance/.codex/worktrees/performance-first-round/smash-suite
先读任务定义 /Users/bytedance/.codex/worktrees/performance-first-round/smash-suite/docs/ai/performance-first-round/task.md、已批准 first-round.md、根AGENTS和所属README。仅在任务目录实施。禁止git提交/推送、重写历史、修改主目录/旧基线、下载、管理员鉴权、运行真实模型/完整基准（由主控串行调度）。可跑低负载的定向单元测试，真实推理和全量测试等待主控。
真实探针请准备可由主控运行的脚本放在自己的通信目录；不可直接运行。固定权重/输入路径在task.md。不要读取另一开发角色或verifier通信目录。
必须保留单项代码证据：以下patch只含自己的产品源码变更，不含测试/文档/别人recognize.py函数。可以通过原始文件文本+仅替换自己函数生成difflib统一diff（a/相对路径,b/相对路径），不要git diff整份recognize.py混入另一线。保存每个阶段的自己源码文件SHA。最终代码只保留有效实现，不增加公开API开关/永久实验开关。必要的已有接口保留，不猜测新设备/新格式兼容。
共同文件recognize.py：D独占person_signals函数，C独占observe函数。只用局部patch，读取最新文件再替换自己函数，禁止从启动时旧全文写回覆盖另一函数。其他recognize区域不改。
若沙箱不允许写任务WT，使用exec_command require_escalated进行仅该目录的窄范围写入/补丁（用户已授权独立开发）；不使用osascript、sudo或更改权限。
完成后写output.md，说明实现/准确文件区域/检查结果/未运行项/补丁顺序/风险，停止一切写入供主控冻结。

# D线允许范围与顺序
- 允许：modules/models/keypoint_rcnn/__init__.py；recognize.py仅person_signals；新有意义的姿态模型/人物映射定向测试；自己的developer/d目录。所属模型README的行为说明可最小更新，尚未实测不要标完成。禁止改observe、TrackNet、statistics主阶段、公开前端/API、报告/roadmap。
- 第1步OPT01：在原PoseEstimator单图逻辑加可选Statistics聚合，分别记录输入准备、self.model调用、numpy结果转换；原pose_inference_s仍是整个wrapper调用总时长，现有pose_calls仍为实际模型调用数，person_crops为裁剪数。person_signals中仅传递stats；匹配/回映射计时若加，放包装入口外并注明。不要改采样/裁剪/结果顺序。保存 d01-statistics.patch（基线→01）。
- 第2步OPT02：提供最小的同帧批处理入口并保留既有单图调用。将当前同帧有效人物裁剪按原顺序收集；0跳过，1单图，2一次CPU调用，每图输出按原对应关系逐人处理，保留IoU .3及LK/坐标。禁止跨帧、改crop/resize/线程/精度/设备/阈值。保留RGB .copy。计时与计数解释batch，记录单图/双图批次、图片数量及padding形状所需的有界聚合，不保存全片图像/逐帧日志。保存 d02-batch.patch（01→02）。
- 第3步OPT04姿态copy：只在能证明cvtColor结果独立连续、后续不改值时去掉RGB额外copy。准备真实裁剪数值探针，不自动通过；若不成立保留copy。保存 d04-copy.patch（02→02+04）。
- 首轮只有逐人vs同帧2图变量，避免输入条件框架/自动设备fallback。keypoint输出可能因batch padding改变，报告不能宣称strict等价；用有意义模拟模型测试人物映射/单人/双人/无有效裁剪/空检测，不镜像每行实现。
- 保存真实探针脚本：可接收原参考模型源码路径及候选源码路径/权重路径/原D视频；少量真实帧裁剪通过现有人物检测或明确人工取样，覆盖同帧大小不同的两人，比较copy前后预处理张量、单图vs双图输出差异/工作量/耗时（仅探针，不完整性能结论）。不要跑该脚本，交主控串行执行。

# 主控冻结前复核（第1轮修正）
请在原目录返工，不运行真实模型：
1. d01中的enabled统计保护请贯穿d02和最终版。当前最终_prepare/_infer无条件调用时钟且只检查statistics is not None，导致Statistics(enabled=False)时仍做细计时；仅在statistics.enabled为True时细计时，保留现有全入口pose_inference_s原统计方式。
2. person_signals当前重复实现Torchvision resize/padding计算，并把估算值记为实际padding。请删除这段推导/内核配置访问，避免两套缩放公式与无统计时的额外工作。产品保留batch/裁剪调用数及必要的有界输入尺寸聚合（仅统计开启时记录）；真实padding在自己的小样脚本中使用模型transform的forward hook观察实际ImageList尺寸/补边张量，标清仅小样，不外推全片。
3. _batch作为跨模块调用接口请改为明确的predict_batch，保留单图__call__；更新对应测试/探针。别加入新设备fallback或公开请求开关。
4. 重新生成d01/d02分项补丁与SHA，确保01只诊断，02只有批处理增量；04仍待真实copy探针，可保留空patch。产品source补丁头应有完整相对路径，recognize仅自己的函数，不混入C。
5. D定向单测在共享recognize语法稳定后重跑；若C仍写入，先完成源码、输出并暂停，主控统一跑，不据此误判D算法错误。
完成更新output.md后停止写入。

# OPT04 姿态copy真实前提已取得（第1轮）
主控已串行运行4个真实D帧、8个人物裁剪的小样，证据apps/video-clipper/.runtime/performance-first-round/probes/d-real.json；采样来源d-samples-source.json（实际检测框选择，仅数值探针，非主球员真值/人工标注）。每个copy_check均独立持有内存、连续、不共享输入、像素/张量严格相等、输入未改动。
请仅完成OPT04这处额外RGB copy删除，保存d04-copy.patch（严格从已交付02到02+04的一行增量）和阶段SHA，保留已冻结d01/d02补丁与SHA不变。可把探针中“manual”措辞改为“selected real-frame crops”，不得改检查或原结果。无需运行测试/模型；output.md说明真实copy前提已通过、batch输出存在差异仍待完整D验证。完成后停止写入。不要根据小样修改批处理策略、裁剪、缩放或条件。

# 第2轮：按用户决定移除批处理

2026-10-21 用户明确选择“本轮暂缓批处理”。不要实现条件合批，不再保留无条件合批运行路径/开关/接口。只保留OPT01诊断计时及OPT04姿态RGB copy精简，CPU逐人调用恢复原顺序。C线已完成，不得改其observe/TrackNet代码。

请在同一任务worktree操作：
1. 对照 controller/variants/opt02-batch.patch，只撤销其引入的产品代码：predict_batch、同帧收集/批次计数/尺寸桶，恢复person_signals逐人调用model(crop,statistics=stats)及原有pose_calls/person_crops计数。保持当前_prepare无额外copy以及细分计时。可以反向应用该增量补丁；不要整文件覆盖 recognize.py。
2. 删除仅用于已撤回批处理的测试，不留测试假的batch接口。保留有意义的“统计开启/关闭不会改变单图输出且关闭不读时钟”的检查，重命名为test_pose_statistics.py；尽量简洁。
3. Keypoint README保留实际计时用法，注明仍逐图CPU处理；删掉像现有可用实验能力的predict_batch描述。失败结论在报告中保留。
4. 更新你自己的output.md为第2轮交付，记录已删/保留、精确源码SHA及必要定向检查。可以运行仅该新增测试及git diff --check（当前主控无模型运行）；不要跑全量/模型/改依赖/提交。完成后停止写入，等待主控正式D组合测量。

主控已记录人工确认：230.193秒仍为高置信回合中，batch原始尾229.0秒、导出尾229.5秒误删该点。原始失败证据、增量patch、旧运行均保留，不删除。只清理产品与无用测试。不要读developer/c、developer/docs、verifier通信目录。
