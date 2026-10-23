# OPT20 第1轮独立验收输入

唯一工作树 /Users/bytedance/.codex/worktrees/opt20-flow/smash-suite，branch codex/opt20-flow，基线5bb39fa。验收仅写verifier/output.md和临时runtime；不读developer通信目录，不改实现/报告/标准/冻结、不提交、不合入。可读取task、正式报告、生产实现/需求与冻结证据。冻结files中developer文件只核对SHA，不读取正文。开发已暂停。

用户授权删除D未参与判定的全画面Farneback专属数据流，保留appearance选人、完整Pose、肩腕PyrLK +1/3/5、实际PTS dt和所有规则。检查完整4文件diff，活跃consumer与依赖，确认没有误删有效输出或其它优化。报告在 apps/video-clipper/reports/opt20-flow，任务标准见task.md；本轮无匹配人工标注，但所有最终结果严格相同可以验本项等价简化，不作准确率或30分钟验收。

先核对acceptance-freeze.json中本轮HEAD/files/runtime SHA，静态代码和报告审查，特别逐数组键集合equal_nan、选中trackIDs[58,40]、决策trace、模型工作量和单次计时边界。当前主控正在09B模型回归：在收到主控明确释放之前，不运行pytest、模型、视频解码、构建或性能测量。完成静态审查后暂停，给主控状态；这时不能判完整功能通过。

收到释放后在本工作树依次运行 PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false pnpm run test:backend，再新独立D完整产品API：PYTHONPATH=apps/video-clipper/backend .venv/bin/python -u -m app.benchmark --inputs /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/reports/performance-first-round/inputs.json --cases D-short --models /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models --output apps/video-clipper/.runtime/opt20-flow/independent --report apps/video-clipper/.runtime/opt20-flow/independent-report.json --timeout 1200 。使用require_escalated使MPS与进程枚举实际可用，不安装/下载依赖。该benchmark复用现有HTTP全流程/权重校验/资源采样，不另写runner。

完成后用 docs/ai/performance-first-round/controller/validate.py 独立D caseRoot 主目录baseline/D-short 独立equivalenceJSON，核对所有有效字段、NPZ键集合及13个数组逐值、decisions、工作量与冻结candidate一致，完整音视频decode达EOF。核实模型调用/源帧计数一致，Farneback已移除、PyrLK保留，报告实际耗时，不将单次结果当稳定收益。验收结束再次核对冻结源文件未变。verifier/output.md分别列功能/代码/文档结论、实际命令/证据路径和未验证边界；不得把未执行写成通过。若有问题列可执行修改建议，停止依赖步骤。
