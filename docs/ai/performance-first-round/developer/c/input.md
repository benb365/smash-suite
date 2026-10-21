# 开发第1轮共同约束
工作目录 /Users/bytedance/.codex/worktrees/performance-first-round/smash-suite
先读任务定义 /Users/bytedance/.codex/worktrees/performance-first-round/smash-suite/docs/ai/performance-first-round/task.md、已批准 first-round.md、根AGENTS和所属README。仅在任务目录实施。禁止git提交/推送、重写历史、修改主目录/旧基线、下载、管理员鉴权、运行真实模型/完整基准（由主控串行调度）。可跑低负载的定向单元测试，真实推理和全量测试等待主控。
真实探针请准备可由主控运行的脚本放在自己的通信目录；不可直接运行。固定权重/输入路径在task.md。不要读取另一开发角色或verifier通信目录。
必须保留单项代码证据：以下patch只含自己的产品源码变更，不含测试/文档/别人recognize.py函数。可以通过原始文件文本+仅替换自己函数生成difflib统一diff（a/相对路径,b/相对路径），不要git diff整份recognize.py混入另一线。保存每个阶段的自己源码文件SHA。最终代码只保留有效实现，不增加公开API开关/永久实验开关。必要的已有接口保留，不猜测新设备/新格式兼容。
共同文件recognize.py：D独占person_signals函数，C独占observe函数。只用局部patch，读取最新文件再替换自己函数，禁止从启动时旧全文写回覆盖另一函数。其他recognize区域不改。
若沙箱不允许写任务WT，使用exec_command require_escalated进行仅该目录的窄范围写入/补丁（用户已授权独立开发）；不使用osascript、sudo或更改权限。
完成后写output.md，说明实现/准确文件区域/检查结果/未运行项/补丁顺序/风险，停止一切写入供主控冻结。

# 找球线允许范围与顺序
- 允许：modules/models/tracknet/predictor.py；recognize.py仅observe；新有意义的缓存/调用组/片尾定向测试；自己的developer/c目录。所属TrackNet README可最小更新，未实测不能标完成。禁止改person_signals、Keypoint模型、公开前端/API、报告/roadmap。
- 第1步OPT03：提取复用现有逐帧预处理，保持RGB copy、permute/float/255/resize[288,512] antialias及运算顺序。仅C调用明确传帧身份（选最少接口改动，现有predictor(frames)默认无缓存）。缓存只存单帧预处理CPU张量最多3项，当前视频任务生命周期，结束释放；不哈希图片，不缓存热图/候选或整片。A/D现有无身份调用不缓存且结果/行为不变。帧ID在observe有效单视频内唯一，无需为未知跨源情况引入繁琐检测；生命周期必须明确。
- C顺序[0,1,2]→[1,2,3]→[3,4,5]→[4,5,6]，片尾沿用原逻辑仍模型推理，只复用输入。关注last_candidates与组内返回顺序。用statistics记录有界cache命中/未命中/最多项数/准备帧数，区分tracknet_input_frames仍是每次模型总输入数；不给每帧写日志。保存 c03-cache.patch（基线→03）。
- 第2步OPT04找球copy：仅删除已证实多余的rgb.copy，不能顺便改缩放/数据位置/设备/模型拼接。准备真实RGB数组独立连续性及严格张量等价探针；保存 c04-copy.patch（03→03+04）。
- 测试重叠窗口、最多3项、命中帧输入严格同值/同序、片尾不足/尾部补推理和任务生命周期。可用模拟模型省资源，但必须标明，真实帧和真实模型探针留主控运行。避免面向内部结构的重复测试。
- 准备可接收权重/输入视频/参考源码路径的少量真实帧探针（放developer/c），严格比较原预处理与复用/少copy的张量及真实模型输出/候选；两组三帧及尾部覆盖，记录工作量/缓存内存5.1MiB本体与实际峰值边界。不得自行启动真实模型。

# 主控复核补充（开发第1轮，冻结前纠正）
当前observe源码把frame_ids传给所有场景，包括personal；违反“只C启用缓存”。请仅camera_type==courtside传frame_ids，personal保持predictor(frames)无缓存。片尾C照常传ID。测试须明确personal无ID、无cache hits/无额外缓存。
finally中不要用hasattr兼容猜测，也不要从recognize读取predictor._cache_peak_items私有字段。固定真实类型是TrackNetPredictor，只在C路径清理缓存；清理函数内部可记录已有峰值聚合并释放，不要引入通用适配框架。模拟对象按新明确契约提供必要方法，不以测试替身迫使产品增加兼容猜测。
请修正c03/c04分项补丁和阶段SHA，使其仍独立且不夹杂D函数。共享文件目前已完整，请完成检查后停止写入；真实模型仍由主控调度。

# 真实探针第1次结果（仅修探针，不改产品源码）
主控在冻结测量目录运行probe_real_inputs.py --device mps。实际模型热图和候选4组均严格相等，但tensor_matches4组均False。核对脚本发现RecordingModel存batch[0]（9×288×512），对照却是reference_batch.cpu()（1×9×288×512），形状不同导致误报。请只修本角色探针为同形状严格比较，并在结果中保存两侧shape；保持原产品补丁/SHA不变。不得将检查放宽为数值容差。无需自行重跑真实模型，由主控另存第二次探针结果。output.md说明首探针失败是形状检查bug，原JSON保留，不覆盖。完成后停止写入。
