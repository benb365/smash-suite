# develop 集成后独立核对

## 结论与冻结

本次**集成验证已完整执行**。功能与产品代码通过；发现 1 处当前模块文档的陈旧状态，**文档暂不通过，整体暂不通过**。没有功能回归或合并损坏证据。

冻结 HEAD：`0e2881ae75c4fe2a9d694d02411cb7efd833bb7e`，分支 develop。验收开始、结束 HEAD 相同；588 个已跟踪文件实际内容 SHA 摘要首尾均为 `6e6c117653011cd08c89c9c746189e5232d6a0d27026d409e91a006942afa489`，跟踪文件无变动、暂存区为空。

## 剩余文档问题

**P2：`modules/rally/README.md:76` 仍写“三份真实短片的统计开关输出；尚未完成”。** 三短真实 ON/OFF 已通过首轮独立校验，当前报告、应用 README、路线图也已经更新为确认完成并集成；该句会让从模块入口进入的读者得到相反状态。

这句话来自已验收来源分支，本次后续文档提交对该文件仅改开发环境锚点，**不是集成新引入的产品回归**。此前验收遗漏了这句状态残留，本次按当前实际内容报告。建议只把这一句完成状态改为与已保存报告一致，并保留真实模型/非旧缓存的区分；本角色未修复。除此未发现需要返工的集成差异。

## Git 与内容核查

- develop 同时包含来源任务提交 `548ecec81ede4ecf0c4b07ba1c1e9260e15dbb6a` 与原主线 ideas 提交 `3c4be7920cd1bac77253fb21ce8b07ad941ad97b`。
- merge `4dc29706165b5a85bae94097b47359f05aaf9ff4` 的双父按顺序正是上述原主线、来源任务提交。当前 HEAD 是 merge 之后的独立原文档提交。
- 来源 apps/modules 的 239 个文件逐 Git blob 比较，差异仅为允许的 README、报告状态和证据索引，**无产品/模块/测试代码差异**；所有数值摘要、资源图和采样图不变。公共控制器与此前验收内容一致。
- 九份人类原文档在单独的当前 HEAD 提交中提交：根 README、app README、docs README、media README、models README、三个模型 README、rally README；另有两个小执行记录。九文档变化均为“开发工作流→开发环境”标题/锚点；app/rally README 此提交都仅改一个锚点。
- 原 ideas 页面与文档站配置相对原主线 ideas 提交无差异。Windows 路线图两行相对来源分支逐字相同。
- roadmap 任务 2 已完成，保留日期/报告引用，并明确该保留行是后续参考而非活跃认领；性能优化仅解除前置不可用标识、仍待办，没有新增开发。
- `outputs/` 仍未跟踪、未入库；暂存区为空。没有读写其内容，也没有暂存、提交、推送或删除工作目录。

证据：主目录 `.runtime/performance-baseline/acceptance/integration-verifier/git-structure.json`、`integration-status.patch`、`independent-main-docs.patch`。

## 主目录报告、证据和链接

从**主目录实际路径**解析报告全部本地 Markdown 引用，无缺失。报告相对来源分支唯一变化为第 7 行的用户确认集成状态；全部数值、五表单位、七张表的数据行和其余正文逐字相同。7 表列数分别 8/8/5/6/9/4/2，表头/分隔/数据一致。

当前报告、app README 与 evidence-index 均记录用户确认集成；一次测量限制、C 两次展开失败/原因未证实、原生 signpost 尾部与约八秒窗口范围、未完成 30 分钟/准确率/打包等边界均保留。索引只增加集成元数据和相应 scope，绝对 runtime 根仍是保留的来源工作目录。

主目录 `apps/video-clipper/.runtime/performance-baseline` 是实际存在的本机符号链接，目标为 `/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline`；受 `.gitignore` 的 `.runtime/` 规则忽略且未跟踪。没有复制大数据。主目录相对 raw 引用和公共控制器默认 RUNTIME 均能经此链接访问既有证据。

独立核对 133 个 SHA 引用记录无错误；十成片重新计算 SHA，均与首轮独立解码的实际 SHA 相同。四个有效 raw trace 的文件路径/大小清单及索引 SHA 匹配，分别为 500/457/451/431 文件。大 raw trace/XML 本次未重复全量 hash 或解析，沿用原独立重算；已批准清理的无效 A trace 不当作应恢复数据。

这是**本机证据访问安排**，本地忽略链接不会随 Git 到其他机器；其他机器需按索引准备原始数据或可达路径，不能只克隆仓库就宣称原始证据可复验。证据：`main-paths-and-evidence.json`、`report-and-output-checks.json`。

## 本轮实际执行的验证

已读 `package.json`：`test:backend` 实际脚本是 `.venv/bin/python -m pytest`；`pyproject.toml` 的 testpaths 为 `modules` 与 `apps/video-clipper/backend/tests`。本次在主目录以普通本机权限执行完整同源测试，没有把机械集成时的 24 个 backend 子目录测试称作全量。

实际主命令（日志/临时路径均在指定忽略目录）：

```text
/Users/bytedance/workspace/experiments/smash-suite/.venv/bin/python -B -m pytest -p no:cacheprovider --basetemp=/Users/bytedance/workspace/experiments/smash-suite/.runtime/performance-baseline/acceptance/integration-verifier/pytest-temp
/Users/bytedance/workspace/experiments/smash-suite/.venv/bin/python -B docs/ai/performance-baseline/controller/profile_logic_checks.py
```

- 完整 pytest：**103 passed，1 warning，11.44s**。警告为既有 Starlette/httpx 弃用；realtime 时序测试本轮通过，没有以旧结果覆盖失败。日志 `pytest.log`。
- 公共控制逻辑：**5 passed，1.175s**，纯合成过程。日志 `profile-logic.log`。
- 七表源码列数检查、当前主目录链接检查和 `git diff --check` 通过。
- 未触发 pnpm 自安装，没有下载、修改 lock 或放松策略。未执行前端、打包、实际浏览器渲染、真实模型/媒体重跑、原生采样或新权限鉴权；产品代码与来源逐字一致，此次无需这些重型验证。

冻结日志：`freeze-start.json`、`freeze-end.json`。本角色只写本 output 和主目录本地忽略证据，未改变已跟踪树。待上方单句文档状态修正并聚焦复核后，可闭环整体集成验收。完成，停止写入。
