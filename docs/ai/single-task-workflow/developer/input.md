# 最终本地交付：机械 Git 操作

收到主控本次派发后执行；主控只在收束复核通过并清理临时链接后派发。先读 ../task.md，不读取 verifier/ 或联系验收 agent。只能在任务工作区 /Users/bytedance/.codex/worktrees/single-task-workflow/smash-suite 的 codex/single-task-workflow 操作。基线 2ccf5f60b7638774aded138a8af00801501a72f2。不得修改真实实现或标准。

确认 git status，没有意外 staged 项。只允许本地提交这四个路径：

- .agents/skills/run-task-workflow/SKILL.md
- AGENTS.md
- docs/plan/roadmap.md
- docs/ai/single-task-workflow/

不能 git add .，不暂存 node_modules、outputs、构建目录或其他路径；不处理原目录，不切换／合并／变基，不 push。已验收 skill SHA-256 ae20fba1d0df31cc4d2521b416d7c9eeb7bc991b5581740c0c22a1100e33133b，AGENTS 609ccb96e791596d6c0dfa4187797ec0e1b5f85de05a9df50f67ea02229e6568，roadmap 3306a42ab21ff8fa6d1ffb8c701aa32878a67293cf647deebacf22ad5f69e8e1。先核对三者，异常时报告不提交。

在自己的 output.md 追加本地交付准备检查与执行边界后，明确暂存上述四个路径，检查完整 staged 文件清单和 git diff --cached --check。提交消息 feat: add single-task development workflow。只做一次本地提交；不需要重复演练或产品测试。提交后核对 clean status 和 commit 内容，通知只给 output.md 绝对路径，由主控另读 Git 结果确认。为保持提交后干净，成功后不再改 output.md；失败时在 output.md 如实记录，不用未授权方式绕过检查。

## 本地提交重试

上次因历史 .diff 空白上下文而未产生提交。验收角色已将自身 8 份差异证据改为零上下文格式，并独立核对应用前后结果、增删内容和位置一致；新增证据已检查空白。主控已读取本轮修正报告并准许按原四路径范围重试。实现三文件摘要不变。不要读取 verifier/，不需要重复测试或构建；保留上次失败记录，在自己的输出追加这次准备检查，再暂存、检查、只做一次本地提交并核对最终工作区。成功后不改已提交文件，主控亲自核对 Git。
