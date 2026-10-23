# OPT20 主线集成核对

## 结论

主目录集成输入中的冻结检查全部通过。来源任务提交 `f4772273b112ef358ac5345a18aabae37974ee0a` 的四个生产差异、16 个原暂存路径、目标哈希和保全证据均与验收版本一致。主控提供的主线后端检查为 107 项通过。本轮没有重跑模型、D 视频或测试；按授权范围，将冻结的验收结果在 `develop` 本地集成为一次提交。

## 来源与暂存核对

- 集成前主目录 HEAD 为 `92988bfc7efc33127b988db2c3c7cffe23611944`，当前分支为 `develop`；任务来源提交可解析。
- index 路径集合与 `integration-freeze.json` 的 16 个路径精确一致，所有 staged SHA256/删除状态匹配冻结值。
- 四个生产文件与来源提交内容逐字节一致：`recognize.py`、`players_v2.py`、`trials.py` 和已删除的 `body_features.py`。实现范围仍为删除 D 场景无用的全画面 Farneback 及专属数据流。
- `evidence-preservation.json` 中 13 个接受文件和 38 个运行证据文件的来源/目标哈希及大小均已核对。`task.md` 仅按约定追加主线集成元数据，来源 SHA 作为例外保留；本地源任务提交不变。
- 暂存的专题 README/roadmap 仅包含 OPT-20 与 OPT-09B 的进展投影。两个文件的完整用户规划修改仍留在 unstaged 工作区；`docs/plan/ideas.md`、`optimization-details.md`、两张 SVG、`outputs/` 和运行时文件也未加入本次提交。
- `git diff --cached --check` 与 `git diff --check` 均通过。

## 验证来源与边界

主控在集成前已运行 `PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false pnpm run test:backend`，结果为 107 passed、1 条既有 Starlette/httpx 弃用警告、12.63 秒。本轮依集成输入采用此结果，不重复执行。

独立验收已经通过同输入同权重的 D-short 产品 API 和 `validate.py` 完整结果对照。真实识别、全部 13 个人物信号、选人、决策 trace、工作量及成片在基线/候选间一致。来源专项报告明确未覆盖人工标注准确率和 30 分钟素材，也不将单次计时解释为稳定收益；本次主线集成不扩大这些结论。
