# 已验收首轮的本地提交

目标唯一工作目录：/Users/bytedance/.codex/worktrees/performance-first-round/smash-suite；分支codex/performance-first-round，当前HEAD应为5c946e9e6186d052624ca6f853a62d40f034f6e8。用户已确认本工作流：独立验收通过后仅本地提交，不合并、不推送、不归档工作目录。不要操作主目录，不读其他角色通信文件正文，本输入交接必要事实。

验收：106项后端测试正常权限通过，真实MPS探针严格等价，C/D完整保留组合通过，230.193秒点保留。57份SHA见docs/ai/performance-first-round/controller/acceptance-status-freeze.json，轮次acceptance-closeout-3，已独立通过。必须重新核对这57份SHA，不重复模型/测试。保留01/03/04，batch产品代码已移除，只留失败补丁/证据及墙钟归因限制。

步骤：
1. 检查分支/HEAD/索引，索引应为空；若有意外暂存或源SHA不符，停止报告，不回退他人改动。
2. 构建modified/untracked允许清单。精确允许文件：apps/video-clipper/README.md；docs/README.md；docs/plan/roadmap.md；modules/models/README.md；modules/models/keypoint_rcnn/{README.md,__init__.py}；modules/models/tracknet/{README.md,predictor.py,tests/test_preprocessed_cache.py}；modules/rally/recognize.py；modules/rally/tests/test_pose_statistics.py。允许前缀：apps/video-clipper/reports/performance-first-round、docs/features/performance-optimization/、docs/ai/performance-first-round/。仅此范围；可通过Git操作添加证据/角色记录，无需阅读其它角色通信正文。任何其它变化不要暂存，报告即可。
3. .venv为临时符号链接，不提交/不删除。所有.runtime大证据、权重、输入视频、缓存不提交。不使用git add -A或-f。明确添加允许路径。
4. 在commit前写好自己的output.md，记录允许范围、核对版本/源SHA及staged差异检查；最终提交标识以Git HEAD和工具执行结果为准，不把自指向commit哈希重复写回文件。此记录包含本次提交。若commit失败，更正并报告，不绕过hooks/签名/策略；成功后不再写仓库文件。
5. 暂存允许范围及自己的input/output；检查git diff --cached --check和统计。patch数据仅在本AI目录有格式属性，原字节和SHA必须不变。不得改产品源码或已验收人类文档。
6. 本地标题：perf: reuse courtside frames and refine pose diagnostics。正文说明缓存/两处copy/细计时、batch暂缓及证据。不得推送、合并、变基、归档。
7. 提交后核对HEAD/分支/status/committed paths；预期只剩未跟踪.venv链接。最终消息返回准确SHA及结果；成功后不再改output.md产生脏文件。

此次仅任务目录内提交。自动审批此前拒绝了试图同时同步主目录roadmap的动作，主控已放弃该副作用；不得尝试主目录修改。
