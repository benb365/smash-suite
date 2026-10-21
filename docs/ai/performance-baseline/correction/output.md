# 第二轮修正结果

状态：开发修正完成，等待主控冻结复验。独立验收仍为 `pending`。

## 修改文件

- `docs/ai/performance-baseline/controller/python_profiles.py`：将推导字段和变量改为 `visible_residual`，明确 recognize 分母只取 SVG 中可见入口区间并集，并写入 Inferno 0.1% 最小宽度及两层残余/覆盖限制。
- `apps/video-clipper/.runtime/performance-baseline/python-analysis/A/summary.json`
- `apps/video-clipper/.runtime/performance-baseline/python-analysis/C/summary.json`
- `apps/video-clipper/.runtime/performance-baseline/python-analysis/D/summary.json`
- `apps/video-clipper/reports/performance-baseline/python-summary.json`：保留精简投影并更新来源摘要 SHA。
- `apps/video-clipper/reports/performance-baseline.md`：修正 Python 段落、表头、`interpolate` 与 `people_flush` 的可见残余表述。
- `apps/video-clipper/reports/performance-baseline/evidence-index.json`：更新报告投影和 A/C/D runtime 摘要的大小与 SHA，并核对索引内所有文件引用。

应用 README 没有相关的当前口径错误，因此未修改。未改原始 SVG、日志、原始测量、native 数据或历史诊断。

## 验证

- 使用该 worktree 的 `.venv/bin/python` 从原始 A/C/D SVG 和日志重算摘要。SVG/log SHA 均与原索引一致。
- 将重算前精简投影中的数字与重算结果逐项比较：A/C/D 分别有 149/306/235 个共同数值路径，数值均相等。
- 可见 recognize 入口并集为 4210/12179/32199；可见残余为 1/75/136；A 握手样本 10427；C 栈展开错误 2 均保留。
- controller AST、JSON 产物解析通过；递归检查证据索引中所有文件引用的路径、大小和 SHA 均匹配。
- 当前摘要不再输出 `self_samples` 或 `percent_*_self` 字段；当前报告及摘要不再称分母覆盖完整识别子树或残余是精确值。
- `git diff --check` 通过。

## 剩余问题

C 仍有两次 py-spy 栈展开错误。Inferno 裁剪使窄帧与完整栈覆盖无法从现有 SVG 恢复。单个可见节点残余只是该可见出现真实自身驻留的上界；函数聚合会遗漏被省略的窄出现，不能视为完整函数上界。inclusive 与残余都是栈驻留，不能解释为纯解释器 CPU。以上限制留待独立验收审查；本轮未补采、未重跑模型，也未更改算法或测量数字。
