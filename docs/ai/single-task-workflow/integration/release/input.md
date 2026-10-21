# 最终提交与推送

用户明确同意合入 develop 并推送。主控将在独立集成复核通过后派发本文件，收到本次派发后才执行。只在 /Users/bytedance/workspace/experiments/smash-suite 的 develop 操作；不要读 developer/、verifier/、integration/git/、integration/verifier/ 或联系其他 agent，主控经本文件中转结论。业务与结果只用本目录文档，完成通知只给 output.md 绝对路径。

预期 develop HEAD 为 2ccf5f60b7638774aded138a8af00801501a72f2，已准备 squash 的已验收源为 3b0ef65b42b40912ab36ef0cf5b7d573ef7e7707。主控已将 roadmap 本任务改为“已完成”、移除认领并改绿色，task.md 记录实际人工批准；只有这两份已验收文件及 integration/ 记录与原任务提交不同。skill SHA-256 ae20fba1d0df31cc4d2521b416d7c9eeb7bc991b5581740c0c22a1100e33133b、AGENTS 609ccb96e791596d6c0dfa4187797ec0e1b5f85de05a9df50f67ea02229e6568、roadmap 2c24b19c85b9cb1dd125eeb8449cd4df08fbbdfa7bf5b8ea2f3893bac9e0cef8。

1. 先核对 git status、分支／HEAD、远端地址 origin 为 git@github.com:benb365/smash-suite.git、三份摘要、全部差异范围。outputs/ 只观察未跟踪状态，不读取、不暂存、不删除。任何非授权修改先报告不继续。
2. 用 git ls-remote --heads origin develop 确认远端仍为预期基线，若不同则停在当前状态报告，不强推／擅自重写。
3. 在自己的 output.md 先写真实提交前检查、主控派发的复核结论、待执行 Git 步骤与边界。只暂存四个路径：.agents/skills/run-task-workflow/SKILL.md、AGENTS.md、docs/plan/roadmap.md、docs/ai/single-task-workflow/。不得 git add .；不得夹带 outputs/、依赖或产物。检查完整 staged 文件清单，git diff --cached --check 必须通过。
4. 创建一次集成提交，消息 feat: integrate single-task development workflow。核对父提交为预期 develop 基线、内容范围正确、原源提交不作为父提交（主线不带待确认中间态）、已跟踪工作区干净，未跟踪仅 outputs/。
5. 按用户明确授权普通推送 origin HEAD:refs/heads/develop，不 force、不推其他分支、不新建 PR。再次查询远端 develop SHA，必须与本地 HEAD 一致；记录命令实际结果。
6. 成功后不再改已提交 output.md，保持工作区干净（除既有 outputs/）；主控会亲自查询 Git 和远端确认最终结果，报告中的提交前时态需准确。失败时如实写 output.md，保留现场，不擅自绕过检查或清理其他修改。不要重复已通过演练、测试或构建；不自动领取下一项。需要 Git 元数据写入或网络时按已授权范围申请 escalation。

## 主控派发结论

主控已读取独立集成报告并核对实际差异：本轮复核通过，源码与原已验收提交仅有两份批准的状态文档差异；git diff --check、git diff --cached --check 和当前 VitePress 构建（8.08 秒）通过。未执行产品测试／重复演练，本轮不要求。主控授权按上述清单执行一次集成提交和普通推送。原 pnpm 预检查限制保留，不需要重跑或修改依赖。
