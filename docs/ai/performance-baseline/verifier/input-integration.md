# develop集成后的独立核对

用户已明确确认报告、批准合入develop、保留已完成基线行及报告/原始证据/工作目录，后续可新增基线；又授权原主目录文档另行提交。现在集成与文档提交均完成，开发停止写入。不删除worktree、不push。
工作目录 /Users/bytedance/workspace/experiments/smash-suite，当前冻结为已提交HEAD 0e2881ae75c4fe2a9d694d02411cb7efd833bb7e，分支develop。集成merge 4dc29706165b5a85bae94097b47359f05aaf9ff4，来源任务head 548ecec81ede4ecf0c4b07ba1c1e9260e15dbb6a；当前head应是其后的独立原文档提交。
不读correction/或其他角色通信。读取实际git/README/roadmap/报告/代码、公开证据与自己的既有输出。只写本角色output-integration.md及本地忽略.runtime/performance-baseline/acceptance/integration-verifier/日志；不改实现/报告/索引，不提交推送采样或鉴权。

独立核查：
1. develop包含来源head与原主线ideas提交3c4be7920cd1bac77253fb21ce8b07ad941ad97b；merge双父正确；产品/模块/测试与来源分支逐字相同；九份原文档只在单独后续文档提交（app/rally README应仅开发环境锚点），outputs未跟踪未入库、索引空。当前已跟踪树不得变，结束再核HEAD。
2. roadmap任务2已完成，进行中表保留已完成日期/报告引用，明确后续参考非活跃认领；Windows不改，性能优化仅解除依赖并保持待办，未擅自开展。报告/app README/evidence-index现行状态均用户确认集成，保留一次测量、C缺样、native尾部/阶段范围、未30分钟/准确率/打包等边界。报告数值/表头单位/图表/原始源均与任务分支一致；集成只允许对应状态元数据变化。
3. 报告从主目录实际解析全部本地Markdown引用，不能只在来源worktree解析。大型原始数据保留旧worktree，主目录apps/video-clipper/.runtime/performance-baseline是本机忽略目录链接，指向保留的来源runtime；该本地链接不进Git、不复制大数据，确保相对raw链接与当前控制器默认ROOT可达。索引绝对runtime根仍保留来源路径。确认所有原始数据保留，并明确这是本机证据，其他机器需按索引准备。
4. 检查package.json test:backend真实命令与pyproject testpaths，实际以主目录绝对.venv/bin/python -m pytest运行完整同源检查（应覆盖modules+backend，预计103项；此前机械集成只跑backend子目录24，不能把24称全量）。不触发pnpm自安装，不下载/改lock；需要系统进程枚举时普通本机权限执行测试。执行5项公开profile_logic_checks，Markdown7表列数与git diff --check。源码无前端契约变更不要求前端/包/真实模型重跑。若现有realtime时序测试失败，按事实核查不能掩盖。

输出实际检查/命令/计数/日志与功能、代码、文档独立结论，是否完成集成验证、任何新问题。明确未执行项与本机raw访问限制。完成停止写入，主控读取与你的冻结HEAD匹配后采用结论。后续只本地提交你的输入/输出等小执行记录，不改实现。
