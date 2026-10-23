# OPT-07A develop 集成复验结果

## 结论

代码、冻结暂存内容、数据证据和后端回归均通过。针对旧托管 worktree 归档顺序的状态措辞已复查：任务记录现在明确写明证据已复制并校验、worktree 仍保留，待集成提交和验证完成后再归档，与当前文件状态及任务 skill 顺序一致。

## 代码与暂存范围

- 当前分支为 `develop`，HEAD 为冻结基线 `94a8465`；本轮未提交。
- 冻结清单的 21 个暂存文件均与 `integration-freeze.json` 中 SHA-256 一致；除专题 README 与 roadmap 两个明确保留草稿的路径外，工作文件也与冻结暂存内容一致。
- 暂存的 predictor、测试和模块 README 与已验收任务提交 `616eb68` 字节一致。与基线相比，生产 predictor 只有一处变化：`.float() / 255` 改为 `.float().div_(255)`。
- OPT-07A 的严格模型输入、完整 A/C 识别对照和报告均作为冻结文件保留；没有改变行为或追加模型实验。任务记录、专题与 roadmap 将 OPT-07A 标为完成，整体性能优化仍进行中，OPT-06 继续。
- 明确排除的 `ideas.md`、性能基线 SVG、`optimization-details.md` 和 `outputs/` 均未进入暂存差异；其他现存用户草稿保留在工作区。
- `git diff --cached --check` 与 `git diff --check` 均通过。

## 证据搬运

`evidence-preservation.json` 列出的 28 个目标文件全部存在，合计 934,772,288 字节；每个文件的大小与 SHA-256 均匹配清单。源 worktree 中 28 份对应文件仍在，符合 revision 2 的明确状态；本次不执行归档。

## 回归测试

运行 `PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false pnpm run test:backend`：107 项通过，1 条既有 Starlette/httpx 弃用警告，耗时 12.58 秒。该入口执行 `.venv/bin/python -m pytest`；没有安装 JavaScript 依赖，也没有改变安装安全策略。未运行前端、模型或视频实验。


## revision 2 状态复查

revision 2 冻结清单仍有 21 项；所有暂存 blob SHA 均匹配，其中 `docs/ai/opt07a/task.md` 的 SHA 与更新后的预期值一致，工作文件也与暂存 blob 一致。其余 20 项未变且继续匹配冻结值。纯措辞修改没有改变生产代码、测试或既有实验结果；未重跑后端测试。
