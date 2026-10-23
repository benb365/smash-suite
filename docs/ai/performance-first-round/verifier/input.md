# 首轮性能优化独立验收：第1轮

## 目录与角色

唯一目标工作目录：/Users/bytedance/.codex/worktrees/performance-first-round/smash-suite，分支codex/performance-first-round，基底5c946e9e6186d052624ca6f853a62d40f034f6e8。
只读本输入、task.md、controller批准证据、实际源码/所属文档、apps/video-clipper/reports/performance-first-round*及其.runtime原始证据和原基线。不读developer通信目录。只写verifier/output.md及本目录临时核对结果，不改实现/标准、主目录、依赖、Git提交或其他目录。

最终冻结后，验收轮次和具体SHA会追加于末尾；没有冻结信息不得执行验收。开发已暂停，主控不得在验收期间修改实现。

## 用户已确认范围

本轮分别验证01/02/03/04，再组合有效项。现用户已明确本轮暂缓批处理，产品必须移除predict_batch、批次处理和测试；保留失败补丁/测量及其方向价值。**不是要求把所有候选都优化成功**；验收对象为01诊断、03缓存、04两处复制简化与完整证据，02有提速但误删的失败结论须准确。

保留模型、CPU/MPS设备选择、线程、采样、裁剪、缩放、阈值、LK、导出balanced与0.5秒缓冲。无前端/公开API契约变更，无粗筛、重复解码复用、条件合批、语言迁移或算法稳健性修复。

- OPT01：仍逐图CPU姿态调用，已有pose_inference_s为包装器父项，新增输入准备/模型调用/结果转换嵌套统计，关闭时不读额外时钟且结果不变。
- OPT03：仅C明确帧号复用最多3个CPU预处理张量，单视频作用域；窗口、模型调用、候选及片尾不变，结束/异常清空。A/D无帧号不缓存。
- OPT04：仅两处RGB额外copy删除，所有权/连续性/像素和张量/输出等价有真实证据。微小copy单次秒数不能宣称稳定提速。
- 效果：优先完整原始区间、导出等价。真>3秒不新增漏失/减少有效对打内容，真<=3秒损失须逐例人审，不新增独立非回合；不能用旧媒体SHA不符的标签/缺失缓存证明通过。
- 用户明确确认D的230.193秒球尚未落地，应为强置信回合中；batch导出尾229.5秒误删该点。保留版本须覆盖该点。用户提出改善原有算法逻辑后可能规避批处理误删，这是后续假设，不是本轮通过结论。

## 要独立检查

1. 功能：重跑最终后端测试及真实小样关键核对；完整测量读取全部真实证据，有疑点才补对应重跑。重模型/视频解码与完整测量串行，不与其他模型任务并发。
2. 代码：核对git差异、补丁和源SHA。无batch残留，无无用兼容/调参框架；统计关闭/映射/输入数值、缓存命中淘汰、身份作用域和异常清理风险得到覆盖。核对计时/工作量/资源口径；新增成本包含在完整总时间。
3. 文档：只检查本轮更改和受影响入口，结构简洁、单位/状态/推断边界清楚；后续批处理有性能价值但暂缓，不误写成方向无效。原基线及Windows后续任务保留，主线总性能任务仍进行中。

后端入口package.json的test:backend就是`.venv/bin/python -m pytest`。pnpm入口曾在进入Python前触发JS自动安装，被watchpack包的供应链锁文件校验阻止；未放松策略/改锁文件。可以直接执行该实际Python命令，并核实此替代和入口限制已准确披露。无需重试下载或修改依赖。前端未变，不跑前端检查。

可用真实C探针：controller/probe_tracknet.py，经主控批准复制为公共验收入口，不需读开发目录。使用controller/run_probe.py固定torch4/OpenCV1，显式PYTHONPATH指向目标worktree，`--device mps`、固定C视频/ball_track权重、`--reference-source`取git基底的TrackNet源码临时文件；先核对探针中的原预处理字面公式与实际基底。它严格核对真实7帧的4个重叠窗口、输入张量、热图和候选。默认不额外跑整段全组。

还须独立核对无帧ID的真实输入不启用缓存且张量保持基底数值；可以使用同一真实短片的少量帧和录制模型输入的检查，不必再全量A。D按最终完整输出及保存的8裁剪原始数值证据核对，单图计时开关须重跑。

## 证据入口

- controller/freezes/*.json：每个run的三份真实源码SHA、所用补丁及普通用户UID、前后源未变；controller/variants保存增量补丁，不得把OPT02失败补丁算入最终交付。
- controller/c-measured-coverage.json：组合C测量源码重建等于冻结SHA，实际TrackNet整文件和observe AST与最终相同；D诊断函数在C不执行。
- .runtime/performance-first-round：opt01-d(D原版计时)、opt02-d(无条件batch失败)、opt03-c(C缓存)、opt04-a(A仅copy)、combined-c(C缓存+copy)、combined-d(最终源码保留组合D)。每个CASE含result.json、resources.jsonl、evidence/result.json/statistics.json/output.mp4等真实结果。
- .runtime/performance-first-round/probes：c-real-r2.json为修正比较张量维度后的有效严格结果；c-real.json保留早先探针比较形状错误，不是候选算法变化。d-real-copy-removed.json为8裁剪copy前后单图严格对照，其中batch差异不属于最终实现。d-samples-source.json说明检测框仅用于数值，不是人工主球员/回合真值。
- 原基线只读目录：/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/baseline。
- 正式报告：apps/video-clipper/reports/performance-first-round.md；inputs/validation/measurement-summary/d-batch-changes.json及截图归同名子目录。原大证据未加入Git而保留本机；报告应明确路径/复跑边界。

输出分别给功能/代码/文档结论与整体是否通过、命令和实际结果、被验版本SHA、必要阻塞/风险。不要只凭开发结论或状态completed判通过，不因单次总耗时小幅反常夸大收益；有疑点应定位并写明。

## 验收已冻结，可开始

- 本轮实现：`controller/acceptance-freeze.json`，轮次acceptance-1；基底及所有被验代码/测试/人类文档/正式小证据SHA见该文件。三份产品源码与最终完整D测量相同。root与开发角色均停止改写被验实现。
- 全部7份真实运行完成，包含新增`opt01-d-control`（与opt01-d的全部源码/依赖快照/配置相同）。最终D295.94秒且区间、导出、全部保存姿态信号与OPT01等价，230.193秒点保留。追加原版339.24秒，首次318.38秒；具体运行时差异尚未定位，报告明确独立墙钟归因不确定，未宣称copy或batch获得确定整段比例。请独立审慎核对是否符合“工作量实证减少、copy严格等价也可保留”的已确认标准，而不是默认判性能收益通过。
- 主控最终Python后端106 passed、1既有warning；你须独立重跑。当前无其他模型/测量任务运行，可串行运行你的关键真实小样核对。正式报告尚标准备验收；你完成后主控仅同步事实状态，再请你复核状态变更。
- 核对正式证据时对照最终版本与相关路径等价，不把全文件不同但不执行的D函数变化当作C需要盲目重跑的理由；也不得跳过真正的新路径验证。

请开始并按本输入规定输出到verifier/output.md。

## 主控补充发现（未修改被冻结实现）

`git diff --no-index --check /dev/null controller/variants/opt01-statistics.patch`会将unified diff中必需的空白上下文行（一个空格）标为trailing whitespace。首次普通git diff --check只覆盖已跟踪文件，未包含新patch数据文件。当前补丁SHA与原运行来源须保留，不能为去空白破坏patch语法/改写已冻结证据。请独立识别产品空白和补丁数据格式的区别，并在报告中给最小处理建议；主控待你完成后再处理，当前不修改冻结文件。

# 第2轮：只复核验收状态与补丁数据属性收口

第1轮正式输出已由主控读取，轮次、56份SHA及三份产品源码匹配。根据信息仅更新8份人类文档的验收事实/状态和链接，新增docs/ai/performance-first-round/.gitattributes；产品代码、测试、数字与全部patch字节未改。主控已验证改变范围只在这些允许文档，冻结文件为controller/acceptance-closeout-freeze.json（acceptance-closeout-2，57份SHA，closeout_changes明确列出）。

请独立复核实际文档差异和新属性范围：任务分支首轮“已完成，待人工确认”，未集成/未推送；整体性能优化任务5仍进行中；01/03/04已验收保留，02暂缓，独立墙钟收益不确定等限制和原基线/Windows任务保留。新属性仅让本AI目录的unified-diff空白上下文按数据保留，不放宽产品源码空白规则；确认patch的SHA不变、无索引和产品空白检查符合预期。无需重复未改产品的整套测试或模型运行；如发现真正实现变化则不要继续按仅文档收口判。

主控还转交一处流程偏差供你独立判断：文档整理角色在收口时意外读取了verifier/output.md，违反不读对方通信目录的规则，已停止；它只在你第1轮功能/代码验收完成之后改状态文档，三份产品源码及测试SHA未变。请你仍不读开发通信目录，按实际最终文件及冻结差异复核，不采用该角色报告替代独立结论；若你认为这影响某项独立性，请明确指出范围和必要措施。

请在你自己的output.md保留第1轮记录并追加第2轮最终结论，或先存output-round1.md再写output.md。写完后停止；不要提交/改实现。

收口后可删除你本轮临时生成的reference-tracknet-predictor.py基底副本（它可由固定Git基底重新导出，JSON已有参考SHA），保留实际探针结果JSON和验收输出；这不涉及修改被冻结实现。若仍用于本轮复核，完成后再清理。避免把重复基底源码作为新维护代码提交。

# 第3轮：仅专题表两格状态复核

第2轮结果已读取，主控批准只将专题README首轮表OPT-01/03的状态从进行中同步为已完成。主控已核对相较acceptance-closeout-2的57份冻结文件仅docs/features/performance-optimization/README.md一份变化，其他56份（含所有产品/测试/数据/属性）SHA相同。新冻结controller/acceptance-status-freeze.json，轮次acceptance-closeout-3。

请只复核这份表和SHA差异，确认01/03/04为已完成，02仍待办且本轮暂缓；顶部首轮已验收、待人工确认集成，主线总任务5仍进行中。无需重复已通过且未变化的模型、全套测试或全报告检查。将该轮最终整体结论追加你自己的output.md，然后停止。主控将读取匹配轮次/版本结论后才本地提交，不合入/不推送。
