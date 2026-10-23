# 资料整理轮次 1

工作目录：/Users/bytedance/.codex/worktrees/performance-first-round/smash-suite。
只整理实际测量，禁止修改产品源码、方案标准、模型、依赖和其他角色通信目录。不要运行模型或测试。主控仍在执行独立单项测量，不要改运行中的源文件。

允许读 controller、apps/video-clipper/.runtime/performance-first-round、已批准专题及旧基线公开报告/原始结果，不读 developer/d、developer/c 或 verifier。允许写本目录 output.md，以及 docs/ai/performance-first-round/controller/summarize.py。先实现可重跑的汇总脚本，暂不改人类报告。

脚本扫描所有已完成的 run/CASE/result.json 和 evidence/statistics.json、resources.jsonl，将摘要 JSON/CSV 和静态 PNG 资源曲线保存到 apps/video-clipper/reports/performance-first-round/measurement-summary/。不复制视频或原始长日志，不改既有原始数据。每条记录含 run、case、total/preparation/recognition/rendering（秒）、子项计时/计数、CPU观测峰值（单核百分比）、RSS观测峰值（GiB）、MPS分配/driver观测峰值（MiB，分列不与RSS相加）、工作区峰值（MiB）、剩余磁盘最小值（GiB）、样本数、最大间隔/采样错误。曲线时间从真实benchmark时钟开始（秒），CPU/RSS/MPS/工作区各列清楚标单位；无有效数据不能画成零。用现有matplotlib，无新增安装；资源很轻，串行处理每个已完成运行即可。

当前完成 opt01-d / opt02-d；opt03-c 正在运行，仅 completed 才纳入。源差异与等价判定由主控处理；不要据秒数自动判定通过/失败或百分比稳定收益。输出记录脚本用法、实际扫描结果、缺口，停止写入等待下一轮。

## 补充修正（同轮）
主控已读脚本：请将扫描范围从 opt*/*/result.json 改成 */*/result.json，覆盖 combined-c 及后续组合，不扫描 evidence 层的result。绘图设置本机已有中文字体（例如已验证可用的 PingFang SC），避免中文缺字；不要安装字体。请检查源目录ROOT计算。输出说明里的运行命令使用本工作目录 .venv/bin/python；该环境已安装matplotlib。只做这几处修正，不执行脚本/模型/测试，C组合正在测量。完成后停止写入。

# 第2轮：独立验收通过后的文档状态收口

主控已读取独立验收第1轮正式输出：56个冻结文件SHA均匹配，功能/代码通过；106项后端测试正常权限复跑通过，真实MPS的C四窗口及无帧ID探针严格一致，最终D区间/导出/保存姿态信号与原版相同，230.193秒点保留。文档内容通过，只需把过期“准备/待独立验收”状态同步，随后验收方再复核状态。该结论由主控批准交接，你不读取verifier通信目录。

只修改下列文档的当前状态/必要链接：apps/video-clipper/reports/performance-first-round.md、apps/video-clipper/README.md、docs/features/performance-optimization/{README.md,first-round.md}、docs/plan/roadmap.md、modules/models/README.md、modules/models/{tracknet,keypoint_rcnn}/README.md。保留所有数值、效果边界、原报告/证据，不改产品代码、测试、测量工具或参数。

收口口径：
- 首轮实际保留01诊断、03缓存、04两处copy；02调用减少，但有用户确认的误删，本轮暂缓，不实施条件合批，也不把8.62%当确定独立收益。原版318.38/339.24秒已披露运行时原因未定位。保留方向价值和后续算法稳健性改善后重评假设。
- 本任务分支的首轮状态为“已完成，待人工确认”，报告/专题/入口说独立验收通过、等待人工确认集成；未合入/未推送。整个路线图任务5性能优化仍“进行中”，Windows任务及原基线行保留。只能更新任务worktree里的文档，不碰主目录。
- OPT01/03/04表内本轮子项可记已完成，OPT02仍待办（本轮实验完成但暂缓采用，后续待评），避免把所有优化方向标完成。专题当前下一步等待人工确认首轮集成，后续方向仍逐项讨论、不自动开发。
- 正式报告增加独立验收摘要，链接执行目录verifier/output.md；主控稍后完成最终状态复核和本地提交，不需要编造提交号。

另外，主控发现统一差异patch的空白上下文前缀（单空格）被Git无索引空白检查当作尾随空白，必须保留原patch字节和SHA。为让完整Git差异检查按数据格式处理这些文件，请仅新增 docs/ai/performance-first-round/.gitattributes 两行：注释说明unified diff上下文前缀是需按字节保留的数据；规则 `*.patch whitespace=-blank-at-eol`。该规则只作用于本AI执行目录的patch数据，不改变产品代码空白检查。验证`git diff --no-index --check /dev/null docs/ai/performance-first-round/controller/variants/opt01-statistics.patch`是否在该规则下通过；不要修改patch、全局Git设置或其他属性。如规则无效只报告，不添加其他绕过。

更新后执行git diff --check、受影响本地链接检查，不跑后端/模型、不暂存/提交；把改动路径、验证及产品源码SHA未变写回你自己的output.md，然后停止写入。

补充：正式报告首条仍有“C缓存可保留进入验收”，请同步成已验收保留；正文若有“尚待独立复验”也一并更新，避免同一报告状态自相矛盾。仅状态措辞，不改数字/结论边界。

# 第3轮：两格状态定点修复

第2轮独立收口复核已完成并停止：产品/测试/数据及patch均未变，补丁属性范围与流程偏差影响边界已独立确认。唯一不一致是专题README首轮表OPT-01、OPT-03的状态单元格仍为“进行中”，虽然顶部/路线图已说验收通过，OPT04已完成。

只修改 docs/features/performance-optimization/README.md 的这两行最后状态列：OPT-01→已完成，OPT-03→已完成。保留它们“集成待人工确认”的进展说明；若已在表前或顶部说明集成待确认无需重复写。其他行（尤其OPT02待办）、正文、数字、属性、源码、测试、报告均不要改，不读verifier或其他开发通信目录。

运行git diff --check，在自己output.md追加已改两格的记录后停止写入，不提交、不跑模型或测试。主控随后重新冻结并请验收方只复核此表。
