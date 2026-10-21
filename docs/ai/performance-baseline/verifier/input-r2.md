# 第二轮独立复验

## 生命周期、隔离与冻结
继续你自己的第一轮独立验收上下文；只在 /Users/bytedance/.codex/worktrees/performance-baseline/smash-suite 操作。先读 task.md 的新增第二轮段落。不要读developer/、correction/、其他角色input/output通信。可以读取你自己的第一轮verifier/output.md及自有acceptance/r1-verifier证据，沿用第一轮已经完成的独立事实核对，但本轮修正必须独立核验。所有开发已停止，主控只写未冻结的任务/执行状态。

版本r2-20261021-svg-semantics，精确文件SHA见../controller/acceptance-freeze-r2.json。先独立复算本轮全部文件及r1→r2差异，结束再次核对。产品147实现与输入/模型/原始SVG/log/trace/视频输出不可变；本轮没有新增测量/鉴权，任何变动都必须说明。若冻结不符停止。

## 本轮唯一修正目标
第一轮发现SVG绘图阈值0.1%省略窄帧，父区间扣可见子区间不等于精确self，也不能保证完整识别分母。现改为visible_residual与可见识别入口并集，保留原数值，产品和实测未改。请独立审查：
- controller/python_profiles.py 所有推导字段/说明是否准确，不保留误导self_samples兼容别名。
- 单可见节点残余是该节点自身self上界；函数聚合遗漏自身窄出现，不能称完整函数self上界。inclusive仅覆盖可见出现，分母仅可见识别入口并集。二者都不能叫纯解释器CPU。
- 实际原SVG/log重算，保持A/C/D可见recognize并集4210/12179/32199、残余1/75/136，A等待10427、C采样错误2及全部原始SHA不变。对你第一轮重算结果逐字段比较，除必要字段改名/解释/时刻外数值不变。运行时在内存调整本轮输出到acceptance/r2-verifier，不覆盖当前原摘要或旧独立证据。
- 三份runtime/python-analysis summary、report python-summary精简投影及全部SHA引用同步，原图与正式计时不变。所有当前报告含interpolate/people_flush及语言建议的解释不误称精确self/完整分母。历史第一轮报告/通信保留原说法不算残留bug。
- 当前报告和evidence-index独立验收状态仍待复验，不能先标通过。人类报告不引其他角色通信目录。
- 独立核对本轮索引、修改行、语法/空白和git diff --check；根据变更范围执行必要聚焦检查。第一轮103后端/5控制/10视频完整解码和原生全部XML重算已独立完成且产品/原始证据未变时，无须重复重型验证。明确哪些结论沿用首轮有效证据，哪些本轮新执行。

## 输出与停止
只写本轮verifier/output-r2.md和自有runtime/acceptance/r2-verifier日志，不改任何实现/人类文档/索引/标准/既有证据，不提交不推送不鉴权不采样。输出轮次2、版本、实际树SHA，功能/代码/文档分别结论及整体是否通过，具体剩余问题。通过后主控会做仅工作流状态收尾（报告/README/路线图/索引的验收标记），再请你检查收尾差异。完成后停止写入。
