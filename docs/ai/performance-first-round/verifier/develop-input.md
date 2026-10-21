# develop 集成验证

轮次 develop-integration-1。工作区改为 `/Users/bytedance/workspace/experiments/smash-suite`，不是先前任务worktree。冻结文件 controller/develop-freeze.json（同一 docs/ai/performance-first-round/ 下）。该工作区在 develop 的未提交合并中，HEAD为5c946e9，MERGE_HEAD为已独立验收的所选提交8614c3c。没有冲突。用户已授权实际OPT03/04合入、不推送；当前文档描述该单次集成提交的交付状态，只有检查通过后主控才完成提交。实现相对8614c3c未变。

只读自己的本输入、当前实现、必要人类文档、冻结和历史原始证据；不读取developer通信或开发会话。可以读自己的integration-output.md及历史验收结果。仅写本目录 verifier/develop-output.md 和自己的 develop-* 检查日志/临时结果，不修改实现或标准；开始/结束核对冻结。

## 检查

1. 合并无冲突、仅OPT03/04代码，三个源文件及缓存测试与8614c3c严格一致，OPT01专用测试仍不存在。以文件blob/sha判断，不把旧整分支diff误读为新增批处理。历史测量JSON/CSV/PNG及patch不变；除已明确的本机原始文件位置说明外，证据数据不改写。
2. 运行集成后端测试 `.venv/bin/python -m pytest`；它就是package.json定义的test:backend。已知普通沙箱的sysctl枚举权限会令3项失败，因此直接在正常用户扩展执行权限下运行，不用sudo、不安装依赖。保存真实完整stdout至verifier/develop-backend.log，记录实际结果（预计105项），不复制旧输出冒充新检查。此前数值探针无需重跑，因为源文件完全未变，本轮不新增性能测量。
3. 主控只改状态/入口：专题、首轮方案、结论报告、三个模型README、应用README、路线图、证据索引本机位置、AI恢复入口。检查简洁准确：首轮03/04在这次提交中完成集成，尚未push；整体任务5仍进行中、首轮认领移除、基线已完成引用和Windows认领保留；任务3只补D子项为OPT02前置，不能把整项任务3设成整项任务5的全局前置。后续方向需用户确认，不自动开始开发。
4. 报告明确历史测量含OPT01统计、交付只03/04，没有新测量；历史106项和当前105项区别准确（删除OPT01专用测试），OPT02已知230.193秒仍为必查项；先改善D找球后证据/结束判断并独立验收，再以改善后的逐人结果重评批处理，不能承诺一定修好。C+1.07%负向观察及原因未知保留。
5. 相对链接和锚点检查、必要差异检查。原immutable summary.csv的CRLF和backend-development.log末尾空行仅这两份可从全分支diff --check排除，其他新文本严格检查。docs/ai链接只供本地追溯，不在文档站发布。
6. 主目录 ideas.md 必须保持SHA `5f0066e40861792a09d79324602ad890ece794fc585534ce8bc8093f3c23bba5`、未暂存；outputs/保持原未追踪状态、不读取。旧主目录四份重叠规划保存在stash `ab32ccc1da55fced5a39ca5647162d4f4fe06d1c`，仅限docs/README.md、docs/plan/roadmap.md、docs/features/performance-optimization/{README.md,first-round.md}。这些早期规划已由本轮经过确认的方案/入口/报告覆盖，如发现有独立未保留内容须指出，不能直接丢弃。原始运行数据仍在主目录对应.runtime：此前168文件逐SHA已独立核对通过，本次确认目标存在、集合和字节数符合preservation清单即可，不必重复读全部1.5GB。原性能基线worktree必须保留。

输出分项结论、冻结版本、实际运行结果及待办。通过后允许主控完成这一个develop集成提交，并在确保原始证据完整的条件下归档本轮任务/测量两个临时worktree；不归档基线。不要自行提交或归档。
