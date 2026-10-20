# 集成执行记录

## 提交前核对

- 当前分支：`develop`。
- 本地 HEAD：`2ccf5f60b7638774aded138a8af00801501a72f2`，与预期基线一致。
- `origin`：`git@github.com:benb365/smash-suite.git`。
- `git ls-remote --heads origin develop` 返回 `2ccf5f60b7638774aded138a8af00801501a72f2`，远端仍为预期基线。
- 三份摘要校验通过：skill `ae20fba1d0df31cc4d2521b416d7c9eeb7bc991b5581740c0c22a1100e33133b`，AGENTS `609ccb96e791596d6c0dfa4187797ec0e1b5f85de05a9df50f67ea02229e6568`，roadmap `2c24b19c85b9cb1dd125eeb8449cd4df08fbbdfa7bf5b8ea2f3893bac9e0cef8`。
- 当前改动仅落在授权范围：`.agents/skills/run-task-workflow/SKILL.md`、`AGENTS.md`、`docs/plan/roadmap.md`、`docs/ai/single-task-workflow/`。未跟踪项另有 `outputs/`；依输入只记录状态，未读取其内容。

## 主控派发的复核结论

主控已完成独立集成复核并授权：本轮复核通过，源码与原已验收提交仅有两份批准的状态文档差异；`git diff --check`、`git diff --cached --check` 和当前 VitePress 构建通过。未执行产品测试或重复演练，本轮无需执行。原 pnpm 预检查限制保留，不重跑或修改依赖。

## 待执行 Git 步骤与边界

按授权仅暂存四个路径：上述 skill、`AGENTS.md`、`docs/plan/roadmap.md` 和 `docs/ai/single-task-workflow/`。确认完整暂存清单及 `git diff --cached --check` 后，创建一次提交，消息为 `feat: integrate single-task development workflow`。确认该提交以预期 develop 基线为父提交、范围正确、原源提交不是父提交；随后普通推送 `HEAD:refs/heads/develop`，不强推、不推其他分支、不创建 PR。推送后查询远端 SHA 并核对与本地 HEAD 一致。失败则如实记录并保留现场，不绕过检查或清理其他修改。
