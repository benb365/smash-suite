# OPT-07A 任务定义

## 授权与路径

- 用户已确认原地归一化、合并 BGR→RGB 与 float32 转换，先验证数值和模型输出严格一致，再做 A/C 识别耗时对照；2026-10-22 补充要求使用仓库 run-task-workflow。
- 主控：当前会话 01a16382-9e48-7fb2-8879-4cfa19c7c62f。任务分支：codex/opt07a-tracknet。
- 唯一实施与验收目录：/Users/bytedance/.codex/worktrees/opt07a-tracknet/smash-suite。
- 起点：develop 提交 94a8465946f97610d91c2bb75b6b9930a93650e5。原目录用户未提交的性能规划、图表和 outputs 均保留；仅原目录路线图新增本任务认领。此前已写的本任务代码与探针已迁入任务 worktree，原目录只撤回本任务自己的实现修改。
- 原 predictor 冻结：apps/video-clipper/.runtime/opt07a/reference/predictor.py；SHA256 df737b3bac7ae2ecba2a8ce6337cb56d7350cc053de54f4b950d997a634679aa。
- 原目录的最新需求属于用户材料，可只读：/Users/bytedance/workspace/experiments/smash-suite/docs/features/performance-optimization/{README.md,optimization-details.md}。不得把用户整份未提交规划混入任务提交。

## 范围与完成标准

1. 只精简 TrackNet 输入预处理，不改颜色/归一化/缩放顺序、288×512、antialias、精度、权重、三帧分组、缓存契约或返回接口；布局、解码重复、其他模型不在范围内。
2. 分别核对原版、仅原地归一化、合并转换候选。真实 A/C/D 短片开头/中间/片尾三帧组，以及 C 重叠窗口，必须对实际模型输入、热图、ShuttlePoint字段和候选字典逐值严格比较；检查原图未变化与缓存释放。合成回归不能代替真实模型。
3. 等价检查通过后，当前原版和保留版在独立进程各完成一次 A-short、C-short 真实识别；沿用 MPS、torch 4 线程及现有生产 OpenCV 设置（setNumThreads(1)）、相同权重与配置；比较原始回合与推导的导出范围，记录识别耗时/工作量/资源。没有成片运行，不能宣称完整产品耗时或画质验收。
4. 每次完整视频读取都到 EOF，不能用提前中止冒充输入完整性；不下载或重编码。输入使用原目录 apps/video-clipper/reports/performance-first-round/inputs.json 的三个短片，校对SHA。模型缓存直接只读复用原目录 apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models，逐一校对ASSETS SHA，不依赖自动下载。
5. 少分配可以作为可验证收益保留；没有稳定提速证据时如实报告。速度明显反常时只补必要对应对照，不私自扩大长片/全组/多轮。
6. pnpm run test:backend、git diff --check 通过；报告与受影响模块入口同步、独立验收分别检查功能/代码/文档。所有关键证据保存到所属模块或应用报告；流水和角色通信留此目录。

## 角色与轮次

当前第1轮：功能、代码、文档独立验收及收尾复查均通过；任务分支已完成，待人工确认。主控按冻结清单保存本地任务提交，不推送、不合入。主控写 task.md、developer/input.md、verifier/input.md；开发只写自己output及授权实现/文档；验收不读developer通信目录，不改实现/标准。验收期间开发暂停，版本冻结后任何改动都须复验。

独立验收通过后仅在任务分支本地提交，不推送、不合入；分支状态为“已完成，待人工确认”，原目录 develop 保持进行中。用户确认实际交付才可集成。后续已授权队列：OPT-06、OPT-08A、OPT-08C、OPT-09A、OPT-09B、OPT-20；具体尚未确定方案仍先确认。本任务不自动新增后台服务或定时器。

## 恢复入口

先读本文件，再读本角色 input。原始证据目录 apps/video-clipper/.runtime/opt07a/；主控汇总将在 apps/video-clipper/reports/opt07a/。当前真实帧严格检查与A/C识别证据已保存；只采用本轮冻结文件与独立验收报告，不引用旧“通过”字样替代当前证据。

## 当前环境核实

本机实际依赖为 OpenCV 5.0.0。独立无模型核查显示 setNumThreads(1) 后 getNumThreads() 为18，setNumThreads(0) 才返回1；因此此前文档把API请求值写成实际线程数的说法不准确。保留当前生产代码的 setNumThreads(1)，不把线程策略变更混入OPT-07A；所有本轮成对测量使用同一当前环境，按实测元数据报告线程值，不能声称固定OpenCV单线程或与旧环境秒数直接归因比较。preprocess-small.json 与当前原版A的记录值均为18。数值与输出严格一致的标准不变。

## 后续授权与数据缺口

用户已明确选择 OPT-06 先做候选诊断：当前 A/C/D 三短片，源时间每秒首组三张相邻帧、尾部不足三帧不补造、任一热图全局峰≥0.5记录疑似，只记录不跳过分析；核对每条当前保留区间是否有命中并测粗查成本；扩展/实际跳过在新证据后再确认。此授权不改变07A顺序，07A独立验收完成后再开始06。

只读数据核查发现三份当前短片SHA与对应reviewed标注的记录SHA均不匹配（不能用相同路径/文件大小推断同一媒体）；D对应标签还有needs_review。当前带FPS元数据的已确认素材记录最大30fps，未发现可直接支持09B真实>35fps验收的已确认样本。后续改变识别结果的项目仍须补匹配的人工效果证据，不能用07A输出等价代替准确率验收。

## 后端验证入口收尾

本机 pnpm 12.6.0 默认运行前自动检查并安装 JavaScript 工作区依赖，最初因 watchpack@2.6.3 的 registry manifest/release-age 校验未进入 pytest；提权复跑仍相同。`--ignore-workspace` 也仍进入工作区安装，主控中断（exit 130）；已产生的忽略目录缓存保留，未改仓库依赖或安装安全策略。

本机 binary 提供正式 `PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN` 设置。主控使用 `PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false pnpm run test:backend`，只对本次 Python 测试跳过无关 JavaScript 依赖自动安装；脚本实际执行 `.venv/bin/python -m pytest`，107 passed、1 条既有 Starlette/httpx 弃用提示，12.66秒。此调用未安装依赖，没有关闭安装时的供应链安全检查，没有修改项目或全局配置。验收方已独立核对该入口：107 passed、1 条相同弃用提示，11.54秒；唯一文档状态修正与12项冻结SHA匹配，git diff --check通过。生产代码与数值证据保持冻结。

## 2026-10-22 用户确认集成与后续授权

用户明确回复：确认交付合入，继续之后的确定项目和高优先级任务，不需要再确认。该授权覆盖本项集成及后续范围内的方案选择、独立验收后集成，取代此前逐项方案/集成确认的等待边界。仍保留原有功能门槛、独立验收和证据要求，不降低验收标准，不推送。

本次将任务提交616eb68的19个已验收路径与最小集成状态更新纳入一次develop提交；主目录既有性能规划、ideas与outputs草稿保留，不将整份草稿暂存。重叠专题和路线图用已提交版本加本任务增量构造index，工作文件保留用户草稿及当前任务状态。生产差异仍仅归一化一行，集成检查由独立验收方执行。原始证据已复制到主目录并逐文件校验；旧任务 worktree 当前仍保留，待本次集成提交和验证完成后再归档。主线OPT-07A已完成，整体性能优化仍进行中，由OPT-06分支继续。
