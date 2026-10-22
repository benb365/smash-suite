# OPT06 第1轮参照证据只读核查

唯一任务worktree /Users/bytedance/.codex/worktrees/opt06-scan/smash-suite，codex/opt06-scan，起点develop94a8465946f97610d91c2bb75b6b9930a93650e5。先读task.md，不读任何developer或verifier通信目录（含历史任务）。只写本目录reference-audit.json及三个reference-<case>.json（如来源可核实），不改实现或其他文档，不跑模型/视频/测试。

目标：查明现存的A/C/D完整原始回合与导出区间能否作为本次“当前保留区间”的诊断参照，准确区分当前同版本与历史同算法，不把历史成本当当前成本。

A/C现存文件在 /Users/bytedance/.codex/worktrees/opt07a-tracknet/smash-suite/apps/video-clipper/.runtime/opt07a/recognition/baseline/{A-short,C-short}/{run.json,result.json,statistics.json}。对应runner在该worktree docs/ai/opt07a/recognition.py。run.git_commit应94a8465，variant baseline，实际预测器为frozen原版df737b...；run记录physical源码候选fa197...并非实际使用类，需读runner证明load_reference先替换package再导入recognize。其他识别实现与当前develop相同，真实媒体/模型SHA需记录。只读参照源和当前相关Git文件（不读07A角色通信）。

D现存主目录 /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/{input.json,evidence/result.json,evidence/request.json}；对应冻结与变体源码在本worktree docs/ai/performance-first-round/controller/freezes/combined-d.json及controller/variants/等controller目录。结合正式首轮报告与当前Git实现，核查hist final和当前交付版是否仅差OPT01细分计时代码；若涉及算法/参数或不能证明，不得称当前结果。可以用代码摘要/明确差异和现存validation佐证，但不能仅凭报告“通过”字样。若不够，报告需新跑D当前短片基准；主控会决定执行，不要自己跑。

参考输入主目录 apps/video-clipper/reports/performance-first-round/inputs.json。媒体SHA目前已由07A严格探针核实，仍核对参照input/run中的SHA与manifest一致；本轮scan会再哈希实际媒体，不必你再读完整视频。当前D应360e3de...；A e2ea56...；C f270602...。禁止借用旧人工标注SHA，不当准确率真值。

输出审计JSON保留所有依据文件路径和SHA、实际版本/变体/来源、结论与限制。若参照有效，另生成reference-A-short.json/reference-C-short.json/reference-D-short.json，固定字段：case_id、video_sha256、predictions（原样完整dict列表）、export_ranges（原样二维区间列表）、provenance（source path、source SHA、metadata/runner或冻结文件SHA、版本和来源限制）。不要推测未知字段或补造区间。原始结果某种结构若与你预期不同，直接指出真实结构，不加宽泛fallback。

审计不需要泛扫所有历史流水，优先准确文件与必要diff；最多检查相关两个版本/片段，不要花时间重新构建全仓库证明。完成汇报并暂停。

## 第1轮主控发现的最小补齐

主控核查发现 D 证据的外层 `/Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/result.json` 明确保存 status=completed、input_sha256、weights 三模型source+sha256。另有已提交controller/evidence-preservation.json记录该运行模型副本的大小/SHA，current ASSETS相符。请读取这两个准确来源并补齐审计的D模型身份依据，删除“D未记录模型SHA无法认证”的不准确限制，仍保留D为历史同算法输出、不是当前成本和准确率证据的边界。

还有一个必须修正的字段：reference-D-short.json的provenance.source_sha256当前错误地是代码SHA字典，按契约应为source_path指向的原始result.json文件SHA字符串（主审计中已正确记录3a23dd...）。将代码SHA字典放独立source_code_sha256字段，不改predictions/export_ranges。A/C字段保持其有效结果，不扩大历史扫描。

你已将三个小reference放apps/video-clipper/reports/opt06-scan，符合正式证据归属，主控接受该位置；本次继续原处，不复制第二份。只修改自己的审计JSON及reference-D-short.json，逐值复核原始结果与修正元数据、diff check，汇报后暂停。不读developer/verifier，不跑模型、视频或测试。
