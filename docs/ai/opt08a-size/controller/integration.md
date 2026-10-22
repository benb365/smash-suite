# OPT08A 集成准备记录

## 前置状态精确复核

复核 cwd：`/Users/bytedance/workspace/experiments/smash-suite`；branch：`develop`；HEAD：`0467b6590d16e4dc60ecc3ae6aa0a40063da8b51`。以下 repr 是复制前捕获的原始 stdout：

- `git diff --cached --name-only`：`''`
- `git diff --name-only`：`'docs/features/performance-optimization/README.md\ndocs/plan/ideas.md\ndocs/plan/roadmap.md\n'`
- `git status --short`：`' M docs/features/performance-optimization/README.md\n M docs/plan/ideas.md\n M docs/plan/roadmap.md\n?? apps/video-clipper/reports/performance-baseline/overview-product-phases.svg\n?? apps/video-clipper/reports/performance-baseline/overview-recognition-phases.svg\n?? docs/features/performance-optimization/optimization-details.md\n?? outputs/\n'`
- `git rev-parse --git-path index`：`'.git/index'`

因此复制前 index 为空；三项 ` M` 是仅 working tree 修改。现已再次确认 index 仍为空；既有工作区改稿和未跟踪文件保持原样，未暂存。

## 证据复制核对

来源 `/Users/bytedance/.codex/worktrees/opt08a-size/smash-suite`，分支 `codex/opt08a-size`，提交 `a960998b367aea63ca2f10e01059be9e3c542614`。验收冻结清单中的 11 项源码/报告及 15 项运行 SHA 均匹配；来源 worktree clean。14 个验收文件、22 个运行原始证据文件和 TrackNet review sidecar 已保存并逐项核对源/目标 SHA 与大小，清单见 `../evidence-preservation.json`。task.md 按授权更新状态，因此 manifest 同时保留该文件源 SHA 和更新后目标 SHA。报告 viewer 与主目录已有 runtime viewer SHA 相同，既有 runtime viewer 保留。

## 集成状态

任务状态更新为独立验收通过、按授权准备集成；测量基线仍记为 `4910e1e5af66d4baebc8373bc6d138645510a996`。产品代码未改动；集成验证待主控执行。本准备未运行模型、视频或测试，未暂存、提交或推送。
