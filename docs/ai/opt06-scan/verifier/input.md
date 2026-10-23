# OPT06 第1轮独立验收输入（冻结后启动）

唯一目录：/Users/bytedance/.codex/worktrees/opt06-scan/smash-suite；分支codex/opt06-scan；生产基线94a8465946f97610d91c2bb75b6b9930a93650e5。

读取task.md、本input、acceptance-freeze.json及指定实现/证据。禁止读取任何任务developer通信目录。只写自己的output.md和.runtime独立结果；不改实现/报告/标准，不暂存提交。开始/结束核对冻结文件SHA与HEAD；如不匹配停止采用报告。开发已暂停。

## 授权与本轮决定

用户先批准首组三相邻帧粗查诊断，后授权继续所有确定及高优先级任务，不再逐项方案/集成确认。随后增加固定1/2/3/5秒正例扩展几何覆盖、A原生三帧模型成本回放，均实验而非产品改动。主控决定本轮指定候选不采用：C/D为覆盖当前区间须近乎整片，A3s尽管保留61%时间，单次粗查+候选TrackNet成本已无优势。仅对此候选收口，不否定整个动态粗筛方向；真实细查/跳过、缺失观测状态和泛化效果未验证。当前27条原始区间仅每段至少一个粗查命中，不是整段全覆盖或准确率。

## 功能检查

1. 检查A/C/D媒体SHA、ASSETS权重SHA、实际模块路径/代码SHA、MPS/torch4/cv实际18、所有EOF帧数共17127。粗查288×512，每个源整数秒首三张相邻帧，片尾不足三张不补造；confidence实际热图全局最大值；threshold>=0.5。FileFrameSource首PTS归零，不能拼整秒相隔帧。
2. 独立读C/D原片到EOF（无模型），生成各秒首三帧ID与实际PTS，逐项核对保存groups、尾部和解码统计。与MPS测量串行，不能和主控并行跑模型；主控此时不运行模型。
3. 独立重跑A真实诊断，使用scan.py --inputs /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/reports/performance-first-round/inputs.json --case A-short --models /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models --reference apps/video-clipper/reports/opt06-scan/reference-A-short.json --output apps/video-clipper/.runtime/opt06-scan/independent-A-short。新目录，MPS，不CPU替代。核对真实groups分数、原始/export逐段覆盖与正式A一致；时间可波动。工作区需要require_escalated以读MPS/进程，但只跑授权命令。
4. 从逐帧分数独立重算27条raw与export半开区间[start,end)命中，检查无采样/低分/只缓冲命中处理。参照controller/reference-audit.json：A/C原始路径已归档，使用preserved_reference_mirror明确的主目录镜像与SHA；A/C baseline实际加载冻结原版df737；D来源ba0fd88只作同算法区间参照，非本轮完整D重跑/当前耗时。
5. 独立重算正例每帧两侧1/2/3/5秒扩展、裁0/production probe片长、合并相接区间与raw/export未覆盖子区间，核对candidate-coverage.json，不把“每段命中”替代整段覆盖。
6. 检查replay-full/candidate.JSON与.runtime原报告逐字节相同；full1400/candidate859窗，4200帧完整EOF，native起始ID0,3,6...，candidate仅取3s候选并按组内任一实际帧时间半开包含，跳过541，不拼帧/不造球点。独立串行重跑replay_tracknet.py --variant candidate，其他参数同A，output用.runtime/opt06-scan/independent-replay-candidate；重算executed IDs一致。不需再跑full1400窗或三片完整recognize，成本单次仍不能证明稳定速度。
7. A成本结论核对：scan18.093526083s + candidate23.273038125s =41.366564208s，full replay29.529457959s；当前原版完整recognition35.655003875s取07A主目录镜像run或summary。它是省略下游的分阶段观察，不能假称真实产品总耗时或数学下限，更不能将嵌套decode/predictor分项再相加。

## 代码与检查

本轮无modules/apps产品代码变化、模型开关/依赖安装/下载，仅docs/ai脚本与正式报告。内存有界，图像最多三帧+源队列，结束/失败资源关闭，completed仅EOF。检查脚本路径/配置失败显式报错。六项定向测试：test_scan.py、test_candidate_windows.py、test_replay_tracknet.py；git diff --check，并检查全部untracked新文本空白。没有产品行为变更不重复后端全量/前端检查。

## 文档与输出

人类报告应简洁分节，先结论，再覆盖与成本、数据链接、版本和限制。不称召回率/准确率通过；未实施产品跳过不称提速已交付。当前候选不采用是有界试验结论，不冒充整个方向全部完成或原始回合为真值。07A已独立集成4910e1e，本轮保持94a原版，不能混入07A速度。

output.md标第1轮/冻结摘要；功能、代码、文档分别结论；列实际执行、必要修订、未执行与边界。按本轮真实文件作判断。写完暂停；不读取其他角色报告或修改它们。
