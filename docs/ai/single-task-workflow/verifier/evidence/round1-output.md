# 独立验收第一轮

## 结论

**不通过，交回主控返工。** 真实隔离演练已完成开发、三步骤独立验收、文档故障注入与返工、本地提交、人工确认前停止，以及明确模拟批准后的临时本地集成。候选 skill 仍缺少已确认方案的三条明确规则；演练还观察到一次已纠正的工具通知偏差，不能声称全程严格满足仅路径通信。

| 独立步骤 | 判定 | 依据 |
| --- | --- | --- |
| 功能 | 不通过 | 正向、返工与人工门槛实际跑通；控制场景显示完整历史隔离和固定版本的关键要求未完整落在候选 skill，见 F1、F3。一次旧验收通知违反仅路径约束，已拒收并更换检查者 |
| 代码／规则 | 不通过 | F1—F3 是已确认范围中的规则缺口；其余变更范围小，未改产品代码 |
| 文档 | 通过（有命令环境限制） | 本轮文档表述、入口、范围与无关任务保留检查通过，实际 VitePress 构建成功；原 `pnpm run docs:build` 入口被现有依赖策略预检查阻塞，不能把该命令记为通过 |

本报告只读获准真实实现、对应文档及自身通信材料；未读取真实任务 developer/，未联系真实开发 agent。仅写本 verifier 目录及获准临时演练仓库，未修改真实 skill、AGENTS、roadmap、标准，未提交、合入或推送真实仓库。

## 固定被验收版本

- 真实任务 worktree：`/Users/bytedance/.codex/worktrees/single-task-workflow/smash-suite`。
- HEAD／基线：`2ccf5f60b7638774aded138a8af00801501a72f2`。验收前后以下三个文件摘要相同，版本未漂移。
- 实际目标变更：AGENTS.md 5 行新增；roadmap 两个自动协作 workflow 行调整；新增 40 行 SKILL.md。任务记录及依赖符号链接未算作实现。

| 文件 | SHA-256 |
| --- | --- |
| `.agents/skills/run-task-workflow/SKILL.md` | `1669a98f801ad2141076967a8e2f0380b8d48ad4e994982935e4a91a07ddf06c` |
| `AGENTS.md` | `f52767088a6bda8b804e366ef64a325f29891377a85da45facb2304a70ca6b7f` |
| `docs/plan/roadmap.md` | `89abb3f965656ecd6ba65adec73da9ad6b5a8fad8b0b769b176a97e86f4cb2db` |

原始版本摘要、当前候选与差异保存于 [target-manifest.json](evidence/target-manifest.json)、[candidate-SKILL.md](evidence/candidate-SKILL.md)、[tracked.diff](evidence/tracked.diff)。

## 需修复的规则缺口

### F1：没有禁止子 agent 继承主控完整历史

定位：`.agents/skills/run-task-workflow/SKILL.md:18-21`；对应已确认方案第 6 项。

现有文本规定文档中转、工具仅传路径、不得直接交流或读对方目录，却没有规定创建子 agent 时不继承完整对话。使用默认继承方式也能表面满足这些句子，业务上下文仍会绕过输入文档进入开发与验收。独立模拟检查的情景 I 同样明确识别该缺口。

最小补充：明确以独立上下文创建两角色，不继承完整对话，业务只来自获准材料；说明这是上下文与职责约束，不是操作系统文件权限隔离。真实演练的 `fork_turns=none` 是测试主控额外落实，不能证明候选已写明。

### F2：没有写入机械任务的模型成本选择规则

定位：同文件“角色与材料”第 16-22 行（全文无模型选择规则）；对应已确认方案第 4 项。

候选没有说明机械任务优先使用成本较低的可用模型、复杂判断按能力选择。真实演练手动选择 gpt-6-luna，属测试输入和主控决策，不能替代交付规则。按原确认方案补充一条即可，无需执行器或模型配置。

### F3：固定版本缺少暂停开发和变化后复验的明确动作

定位：同文件第 26 行“验收固定本轮版本”及第 40 行交付段；对应已确认方案第 13 项。

现有句子给出固定版本目标，但未明确验收期间暂停开发、最终提交对应验收版本，以及后续实现变化必须复验。独立控制检查 H 区分了原文和其额外推论：这些操作尚不能直接从 skill 中照做。本次测试主控另行暂停开发、记录文件摘要并逐次核对，才排除了版本漂移。

最小补充：在验收开始时暂停开发并固定本轮检查版本；最终提交应对应该版，后续实现变化重新验收。无需规定唯一技术手段。

## 实际隔离演练

位置：`/private/tmp/smash-workflow-fixture-w_o8v2za`。原目录 primary、develop 基线 `ab59130db48db6e7161f57fe5b277261f6d14aad`；标准 Git worktree 为 task，分支 `codex/range-workflow-acceptance`，没有远端。全部业务材料放在其 `docs/ai/range-workflow/`，未用绑定真实仓库的 worktree 工具。

### 正向与故障注入

| 阶段 | 实际行为与结果 |
| --- | --- |
| 正向开发 | 新独立上下文开发 agent 阅读用户请求、requirements、现有代码和候选 skill；真实修复 ranges.py、同步 README、补三项有意义的测试。未事先透露预期实现或疑似缺陷 |
| 首轮验收 | 新独立上下文验收 agent 独立跑功能、代码、文档三步骤，均通过；主控也亲自检查实际差异、重跑 `python3 -m unittest -v`（5 项）和 9 个正常／3 个反向区间案例及 README 示例 |
| 人为注入 | 首轮自然通过后，测试主控只在临时 README 写入“首尾相接会保留为两段”；实现、测试和标准不变。这是人为失败候选，不是自然产品缺陷 |
| 失败验收 | 新独立上下文验收 agent 检查当前摘要，功能与代码通过，文档失败：README 第 3 行与需求和实现相反 |
| 文档返工 | 主控核对具体矛盾，通过 developer/input.md 中转；另一个开发 agent 在原目录、原分支只修正 README，不读验收目录。未采纳验收报告里不必要的示例扩展意见 |
| 独立复验 | 新独立上下文验收 agent 对固定当前版重跑完整 5 项单测、必要行为与 README 示例，并检查代码、文档；三个步骤均通过。主控再检查实际差异及摘要 |

严格通信有一次偏差：尝试复用已结束的首轮验收 agent 时，它通过工具重复了旧“通过”结论并含业务文字，实际 output.md 还是旧版。主控未接受该通知，比对报告和当前 README 后改派新独立上下文检查者，后者正确识别注入失败。该次通知违反“仅路径”要求，保留为执行偏差；没有把它算成验收或进展。后续新 agent 完成通知均只给路径。

功能独立检查覆盖：排序、重叠与相接、包含、分离、重复、孤立零长度、空输入、元组输出、输入不变、不同位置反向区间的 ValueError，以及 README 例子。非负整数二元组是已确认输入前提，未扩展前提之外的兼容校验。

### 待人工确认与模拟集成

- 真实完成了待人工确认停止点：临时任务分支本地提交为 `2f3608eafdc1a6267033a7331b4e5e43e9d8ae92`，worktree 保留且干净，任务为“已完成，待人工确认”。当时 primary/develop 仍是基线，任务“进行中”且认领保留，未合入未推送。
- 然后按已授权测试许可，对上述明确提交写入[仅限临时仓库的模拟人工批准](evidence/rehearsal/simulated-human-approval.md)，才在临时 develop 一次 squash 集成为 `4310f4d9ffbe81b601c451a6cd6dc274e209d822`。该集成提交直接标记“完成”并移除认领，没有提交“待人工确认”主线中间状态。
- 集成环境重跑 5 项单测及差异检查通过；ranges.py、README、测试与 requirements 均与已验收任务分支一致。无关任务行未变，未自动领取下一项。
- primary 最终仍只有原用户修改 ` M user-note.txt` 和 `?? outputs/`；两个文件的 SHA-256 与演练前完全相同，未进入提交。任务 worktree 保留且干净。无远端、无推送。
- 人工批准本身为模拟，开发、检查、提交、临时集成和文件保留验证为实际执行；不构成真实 smash-suite 交付的人工确认或集成许可。

精简原始材料见 [evidence/rehearsal](evidence/rehearsal/lifecycle.md)：保留已确认需求、实现差异、首轮／失败／返工报告、输入与控制输出、停止点、批准和两个目录最终状态。未复制 Git 对象或依赖。

## 明确标注的模拟控制检查

由另一独立上下文 agent 根据候选 skill 作判断，输入与输出分别保存为 [controls-input.md](evidence/rehearsal/controls-input.md)、[controls-output.md](evidence/rehearsal/controls-output.md)。这些是模拟判断，不是实际三轮运行、产品实验或真实暂停恢复。

| 控制场景 | 判断结果与覆盖 |
| --- | --- |
| 未确认启用／标准 | A、B 均不派发开发，先由主控确认；通过 |
| 两轮无提升、第三轮仍停滞 | C 要求第二轮调整方向、第三轮停止相关运行并保存等待；通过。未真实制造三个相同失败轮次 |
| 指标失真 | D 用丢失最后一次击球说明错误代价不同，交用户确认，不擅设替代数值指标；通过。未改算法或评估口径 |
| 中断恢复 | E 复用原认领、分支、worktree、材料并重算停滞计数；模拟判断通过，未实际中断长期进程 |
| 人工要求修改 | F 要求原分支返工复验；模拟判断通过。实际文档返工也使用同一目录与分支 |
| 人工确认前后 | F 保持待确认门槛；实际临时仓库也验证了门槛及批准后状态同步集成 |
| 功能或文档失败 | G 判文档失败不能通过，反馈主控；实际文档故障注入已覆盖。未额外注入功能实现错误 |
| 固定版本／上下文 | H、I 明确指出候选缺少的规则，分别对应 F3、F1；不通过 |

权限、数据、环境缺失的暂停规则仅静态核对第 14、32 行；未额外制造每一种故障。模型能力选择仅静态审查；本次机械任务实际用了较低成本可用模型。

## 文档与工具检查

- skill quick_validate：独立执行，`Skill is valid!`、exit 0。
- 自动发现：本地 Codex app-server 只执行 initialize → skills/list 重扫后退出，实际返回 run-task-workflow、scope=repo、enabled=true、正确候选路径；未启动模型任务。首次 sandbox 内不能初始化 sqlite，按授权 escalation 后通过。
- `git diff --check`：独立通过；演练每个候选和集成也检查通过。
- `pnpm run docs:build`：**命令入口受阻**。现有 pnpm 在执行前检查锁文件，因 registry manifest 缺 watchpack@2.6.3 返回 ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION；没有安装依赖、更改锁文件或放宽策略。
- 实际文档构建：确认 package.json 对应命令为 vitepress build 后，使用现有 Node／依赖在 tools/docs-site 执行 `node node_modules/vitepress/bin/vitepress.js build`，exit 0、7.50 秒；只有 chunk 大小警告。59 个 HTML 页面中未输出 docs/ai、AGENTS 或 skill 页面。
- 文档准确与范围：AGENTS 新入口目标存在，启动与状态说明与正文一致；roadmap 除自动协作 workflow 两行外逐行保持基线，包括其他任务、Windows／性能负责人、优先级与斜体。未新增人类入口或日志导航，未改产品接口。本次不要求产品测试，未执行。

可复核记录见 [static-checks.md](evidence/static-checks.md)。真实原目录末次观察仍为 develop、基线 HEAD，显示主控维护的 roadmap 未提交修改和未跟踪 outputs/；本验收未读取 outputs/ 内容或修改真实原目录。

## 主控后续动作

先补齐 F1—F3，并对修订后的固定候选重新独立核验；当前不能据本轮报告宣布 P0 通过。控制演练材料、临时任务提交与 worktree 均已保留，可复用，不需要重复造功能实现。原 pnpm 入口环境限制和一次工具通知偏差须继续如实保留，不把成功构建或后续纠正改写为原命令／全程通信都通过。
