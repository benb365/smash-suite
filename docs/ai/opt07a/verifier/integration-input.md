# OPT-07A develop 集成复验

用户2026-10-22明确确认交付合入，并授权后续确定/高优先级任务无需再次确认。唯一复验目录为主目录 /Users/bytedance/workspace/experiments/smash-suite，分支develop，当前HEAD仍94a8465，集成尚未提交。来源为已独立验收的任务提交616eb68。本轮只核对集成增量和文档状态，不重复未变的MPS/识别实验；不得读developer通信目录。

先读integration-freeze.json与本input。主目录feature README、roadmap含用户大幅未提交草稿，集成使用已提交版本+07A/认领最小增量构造index，所以这两项以git show :path读取暂存版核SHA与文档；工作文件保留用户草稿及本次状态更新，不要求两者相同，不扩大审查其余用户改动。其他暂存路径的工作文件应与index一致；ideas、SVG、optimization-details、outputs不得暂存。

核查生产predictor.py与tests和模块README字节来自616eb68，生产相对develop起点只有 /255 到 .div_(255) 一行；冻结的严格模型/完整A/C证据保留，无新行为。执行 PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false pnpm run test:backend（限制外权限；仅跳过无关JS自动安装、不关闭安装安全策略），以及git diff --cached --check和git diff --check。不要安装或跑前端，不同时启动模型。

核对集成状态改动仅主控task/执行入口/应用报告/专题/roadmap：07A已完成、整体性能优化仍进行中、06继续；报告历史速度/内存/准确率边界不变。evidence-preservation.json记录28份原始文件934772288字节；可核对每个目标存在、字节/SHA匹配，源/目标均在时按必要性检查，确认后可归档旧托管worktree。原始freeze为任务验收历史，不要求因本轮纯状态变化改写旧SHA。integration-freeze里的index SHA才是本轮对象。

仅写本目录integration-output.md，给功能/代码/文档与集成范围结论，记录通过数和限制。不要修改实现/暂存/提交。主控据报告决定一次集成提交和归档。完成后暂停。

## 纯状态措辞复查

主控将task.md原“复制并校验后归档”改成显式状态：证据已复制校验；旧worktree仍保留，待集成提交和验证完成后再归档。此步骤顺序按任务skill执行，不在集成提交前归档。当前integration-freeze revision2只更新task.md这一项SHA，其余20项与生产/测试均不变。请只复查此措辞与当前SHA，并更新自己的integration-output为最终结论，不重跑未变测试。完成后暂停。
