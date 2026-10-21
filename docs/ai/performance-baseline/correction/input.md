# 第二轮最小修正：Python SVG 计数口径

## 工作目录与隔离
仅在 /Users/bytedance/.codex/worktrees/performance-baseline/smash-suite 工作。先读根AGENTS、README、apps/video-clipper/README、docs/ai/performance-baseline/task.md。你是开发修正角色；不要读developer/、verifier/、其他角色input/output通信。只读本input、实际实现、公共controller证据与应用runtime；只写下面允许的文件及自己的correction/output.md。第一轮验收已结束，所有角色停止写入；当前分支codex/performance-baseline，无提交。按已授权最小修正，无需重新向用户询问。

## 第一轮独立验收发现的P2（唯一阻塞）
py-spy v0.4.2 src/flamegraph.rs opts.min_width=0.1，Inferno会省略宽度不足总样本0.1%的帧。原始A/C/D SVG最小可见宽度18/23/47，与阈值匹配。当前controller/python_profiles.py以可见父区间减可见直接子区间生成self_samples，报告将它称最末Python帧，分母称完整识别子树。这不准确。
对于某个可见节点，残余是该节点真实self的上界；函数聚合还遗漏该函数被省略的窄出现，因此不能称完整函数self上界。识别分母只保证可见recognize入口区间并集。无法从裁剪SVG恢复精确self或完整栈覆盖。本轮保留原图与数值，修正字段及含义，不补采、不重跑模型。

## 允许实施范围
1. 最小修改公共controller/python_profiles.py：所有推导的self字段/变量命名改为visible_residual，recognize分母明确visible入口并集。输出解释写明0.1%省略阈值、单可见节点上界、聚合潜在遗漏/不保证完整函数上界、inclusive只覆盖可见出现，残余/驻留均不能叫纯解释器CPU。不要旧字段兼容别名，不变原有数值和算法。
2. 使用WT绝对.venv/bin/python对既有A/C/D原始SVG/log重算，更新runtime/python-analysis/{A,C,D}/summary.json。不要改原SVG/log、原始测量、native或已有历史诊断。可以保留小的r1相关错误语义诊断，避免重复整份大结果。
3. 更新apps/video-clipper/reports/performance-baseline/python-summary.json的相同精简投影及来源summary SHA，维持现有结构的必要改名；不要粗暴复制完整summary造成不必要膨胀。
4. 最小修正reports/performance-baseline.md Python段落、表头、interpolate和people_flush对应用语及任何误称完整分母/精确self的当前说明，明确两层限制。原始数字/正式总耗时/语言建议结论不变。主动阅读全部涉及self/inclusive/分母的当前报告说明避免遗漏。
5. 更新reports/performance-baseline/evidence-index.json中被修改资产和runtime Python摘要引用的大小/SHA；遍历检查索引，不能只改部分。不要更新独立验收状态为通过，目前仍待复验。人类报告不引用任何角色通信目录，可以引用公共controller执行记录。允许更新app README若确有当前错误口径，不做无关改动。

## 校验与结束
读取实际结构后再改。对原SVG重算后独立比较三场景：原始SVG/log SHA完全不变、inclusive与残余的数值在重命名前后逐项相等，recognize可见并集4210/12179/32199、残余1/75/136、A握手10427、C采样错误2仍保留。检查所有当前产物不再输出self_samples/percent_*_self或误称完整。历史input/output/旧验收证据可保留历史，不全库替换。AST/命令执行/git diff --check适当检查，不需重复103后端或10模型/视频解码，产品147文件不可改。必要写入使用普通本机权限，禁止鉴权、采样、下载、提交、推送。
输出correction/output.md标轮次2与修改文件、验证、剩余问题。完成后停止全部写入等待主控冻结复验。
