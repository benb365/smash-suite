# OPT20 主线集成核对与本地提交

主控已接受第1轮功能/代码/文档验收，任务提交f4772273b112ef358ac5345a18aabae37974ee0a在干净来源工作树；来源base5bb39fa，主目录develop当前92988bfc7efc33127b988db2c3c7cffe23611944（09A后仅docs，生产仍同来源base）。按用户无需后续确认的授权，只本地集成，不push。

主目录 /Users/bytedance/workspace/experiments/smash-suite 已复制且仅暂存本次16文件，freeze列出每个index SHA/删除状态。请核对exact路径集合、冻结SHA、来源任务提交和4个生产差异均与来源验收一致（body_features删除）；evidence-preservation.json的accepted/runtime源目标SHA和大小均验证，task.md只追加主控集成元数据有保留sourceSHA例外。原始baseline已在primary；candidate/independent非home文件已镜像；模型缓存仍canonical，不保留每次复制副本。不改变报告或实现/标准。

主目录已实际运行 PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false pnpm run test:backend：107passed，1已有Starlette/httpxwarning，12.63秒。此为主控提供结果；本轮不再重复测试或模型。source独立完整D已通过，主线生产内容SHA一致即可沿用真实数据，不冒称本轮又跑D。

feature README和roadmap有用户未暂存整版规划草稿，当前index仅从git HEAD做本任务进展投影；不得git add它们，不得覆盖/重置工作区。ideas/optimization-details/SVG/outputs/runtime不加入commit。检查本次生产完整diff与入口自洽，git diff --check和cached --check。

仅写自己的integration-output.md，分别记主线字节核对、采用既有功能证据及主控107结果/未重跑边界。通过后只提交16原staged + integration-freeze.json + verifier/integration-input.md + verifier/integration-output.md，一次本地集成提交 perf: integrate unused D optical-flow removal 。提交后核对index为空、原用户工作区修改仍在，返回commitSHA。不要push/归档，由主控保全后处理。
