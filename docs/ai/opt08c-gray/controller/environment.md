# 本轮独立验收环境补充

冻结的13项源码/报告和7项证据不变。本机受限执行会看不到Metal设备，不能把这次沙箱可见性判为MPS硬件不可用。主控已在同一个worktree以 require_escalated 执行 .venv/bin/python 的 torch 检查，结果为2.8.0、is_built=True、is_available=True；没有切换或安装环境。

此前真实模型运行同样在 require_escalated 环境访问本机MPS。独立验收按原输入要求用相同工作树和.venv，真实probe/完整候选的 exec_command 设置 sandbox_permissions=require_escalated，理由为已授权真实MPS关键验收；不回退CPU、不改环境。沙箱失败与实际提升权限检查分别记录，不当成效果失败。其它原freeze要求不变，开始/结束SHA检查照常。若自动审批拒绝再记录实际拒绝；当前没有拒绝。
