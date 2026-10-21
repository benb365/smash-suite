# 首轮报告整理独立复验

轮次 report-revision-1；实现基点 ba0fd88b4563c5366a5dcdac8c5a941573a1a65b。工作目录 /Users/bytedance/.codex/worktrees/performance-first-round/smash-suite。收到主控启动信号后，先核对 controller/report-revision-freeze.json 中所有文件摘要及改动范围（正文迁移与文档修订），开发已停止；只写本目录 report-revision-output.md，不改正文/实现/标准，不提交。不得读取 developer/ 的输入输出或其他角色通信目录。原验收历史可读本角色自己的输出，但本轮独立核对不能只沿用旧通过文字。

## 用户授权与本轮标准

用户确认将首轮任务阶段报告归 docs/features/performance-optimization；补齐方案简介、统一语言名词，表格让人看清优化前后比较。跨模块方案/进展/阶段总结在 docs/features/<专题>/；专项实验报告和测量证据随所属应用/模块/数据集；执行流水docs/ai。迁移旧正文 apps/video-clipper/reports/performance-first-round.md 至 docs/features/performance-optimization/reports/first-round.md，旧正文删除，无副本/跳转；证据和旧基线不改。同步AGENTS/docsREADME/专题/roadmap/应用/模型等活动引用，历史docs/ai冻结与backup不重写。主目录不改。

本轮仅文档，无产品、模型、测试命令变化；无需重跑模型或后端。分别报告：范围与既有功能/代码证据适用性、数字与结论、文档/排版/相对链接。不得把未复跑功能写成此次重新通过。

- 各OPT方案开头用日常语言说明原流程、改法、目的；诊断不冒充优化提速。
- 同义词统一：预处理、额外图像复制、同帧批处理、完整处理耗时；必要代码标识可原样保留。
- 每个方案/组合明确比较来源（旧基线/本轮原版/缓存单项）；耗时表有优化前、本轮、差额且单位明确；差额从未舍入数计算后舍入。没有的细分旧值写未记录，不造0。Pose复制未做孤立完整流程，不造单项耗时。
- 资源峰值有前后参照，采样口径、缺口/样本保留；不把观测峰值认作精确峰值，不相加统一内存口径。
- 旧D335.08310083299875秒；本轮原版318.3818405410275、追加同源339.23569683311507秒。批处理290.95088320807554比首次原版少27.43秒/8.62%，但随后逐人组合295.94129804102704秒；模型内部耗时运行差异未解释，不可归因到批处理/复制独立收益。相同原版两次源码/依赖/配置/权重/输入/工作量/输出一致，不能解释成已定位的温度/负载原因，不推断稳定范围。
- 旧C137.16650762502104→仅缓存114.02834370918572，单次-23.14秒；C组合114.69371983292513相对缓存+0.67秒。旧A48.0540318749845→复制单项43.559546124888584，单次-4.49秒；不能声称稳定收益/全归因。
- C预处理次数10797→5400（旧值来自旧源码每张输入处理一次，不伪称新增计数）；复用5397次，模型调用3599/输入10797均不变。最多3张量、本体5.0625MiB不等于额外进程上限；完整输出等价。历史预处理18.06秒→9.22，组合9.36。
- D批处理2432张裁剪不变、模型调用2432→1255（1177双图+78单图）；第12段end233→229秒，加.5尾缓冲也漏掉用户确认230.193秒仍回合中的点；第7段end108→108.4未单独人审。当前变体效果不通过，方向保留/本轮暂缓，不实施条件合批。算法稳健性改进可能规避误删仅待验证假设。最终逐人版覆盖已确认点。
- OPT01原版姿态入口159.81267244834453秒，输入.45231089484877884、模型159.30746357422322、返回.025149771943688393；模型99.7%不等于纯网络/Python。历史仅总162.02秒，无细分。解码7.5064/整帧转换6.4229在外部。
- 两处复制真实输入/张量严格等价；Pose8真实裁剪输出严格等价；TrackNet有A单项/C组合、Pose有D组合完整验证。状态首轮待人工确认集成，未合入/推送；整体优化任务未完成/不自动继续。

## 数字来源与独立检查

本轮7次精确数字与资源：apps/video-clipper/reports/performance-first-round/measurement-summary/summary.json；结果对照validation/、d-batch-changes.json；原始apps/video-clipper/.runtime/performance-first-round/。旧正式报告 apps/video-clipper/reports/performance-baseline.md；旧精确result在 /Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/baseline/{A-short,C-short,D-short}/result.json。可读controller的正式冻结/对照事实，但不得读developer通信。

检查所有受影响相对链接与图片存在，活动人类文档不再引用旧正文；不将历史AI引用当失效当前链接要求改写。无新命令变动则不执行已有复看服务命令。git diff --check只针对本轮未提交改动，既有提交中的冻结CSV/日志不改。核对三份源码SHA：recognize.py ee2c0a949522ab6c809bf7da9afb4a4956dda9ad3b6da4fc389e8f0598e8bcd0；keypoint_rcnn/__init__.py 379ed20f3c6e228efecd08828ee8b6b6dc6a89084dd19173163ef1cab9c19316；tracknet/predictor.py df737b3bac7ae2ecba2a8ce6337cb56d7350cc053de54f4b950d997a634679aa。既有JSON/CSV/PNG、基线报告均与HEAD相同。

输出本轮冻结匹配数量、修改范围、核对方法及结果、是否可交付。若问题需正文修改，列精确位置与原因并停止，主控另派修订及复验，不自行修复。

## 第2轮定点复验

第1轮输出已由主控读取：范围、冻结、数据、链接均通过，仅术语不一致。主控已将新报告第7行“不实施条件分组”和第75行“不做条件分组”两处统一为“不实施条件批处理”，其余正文/实现未改。新冻结为 controller/report-revision-freeze-2.json，保留第1轮冻结不覆盖。开发再次停止；独立核对两份冻结只有报告SHA改变，报告相对第1轮仅上述两处术语替换，34项当前SHA及删除项匹配，术语/链接/空白通过后可判本轮报告修订交付通过。只在自己的output追加第2轮结果，不重跑模型/后端、不读developer。
