# 演练子 agent 生命周期与观察

各任务启动消息只传相应 input.md 路径与生命周期指令，业务内容在任务材料中。开发与验收均 fork_turns=none，模型 gpt-6-luna（开发 medium，验收 high）；控制判断 gpt-6-luna medium。

1. range_developer：真实开发；以 developer/output.md 路径通知完成。主控读取文件、实际差异，独立重跑五项单测与 9 个正常/3 个反向区间案例、README 例子。
2. range_acceptance：新的独立上下文，三步骤通过；完成通知为路径。主控保存首轮材料。
3. 主控人为注入临时 README 错误。尝试复用已结束的 range_acceptance 时，其额外工具通知复述旧“通过”结论并包含业务文字；实际 output.md 未更新。主控比对当前 README 和报告后拒收该通知，不将其记作新检查。
4. range_fault_acceptance：新的独立上下文，识别文档失败，功能/代码通过。主控核对 README 第 3 行矛盾成立，通过 developer/input.md 反馈开发；未采纳不必要的示例扩展意见。
5. range_rework：新的独立上下文，沿原分支/目录修正 README；只返工必要描述。
6. range_reacceptance：新的独立上下文，对固定当前候选独立重跑五项单测、需求行为、README 例子并审查代码、文档；三个步骤通过。
7. 主控核对实现版本，提交临时任务分支 2f3608eafdc1a6267033a7331b4e5e43e9d8ae92；先证明 develop 未前进、任务进行中与认领保留，task 标记已完成待人工确认。
8. 对该明确临时交付写入模拟批准，仅临时 develop squash 一次集成为 4310f4d9ffbe81b601c451a6cd6dc274e209d822；移除认领，主线直接标记完成，重跑五项单测与差异检查，代码/README/测试/标准与已验收 task 相同，两个用户文件 SHA-256 未变。

这是实际隔离开发/返工/本地提交/临时集成；人工批准本身是明确标注的模拟。没有真实远端、推送、真实产品改动或真实 develop 集成。已记录的一次非路径通知是通信偏差，不能声称全程零违规；由主控检查发现并替换检查者完成恢复。
