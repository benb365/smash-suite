# 第二轮独立复验结果

## 结论

- 轮次：2；版本：`r2-20261021-svg-semantics`。
- **功能、代码、文档分别通过；本轮整体通过。** 第一轮唯一 P2 已闭环，无剩余阻塞。
- 当前通过范围是本任务确认的六正式性能测量、三短 Python 剖析及 A 额外原生补录、等价检查与限定优化诊断；不代表准确率、浏览器交互、重新打包或 30 分钟产品验收。

首尾独立复算 402 文件，实际树 SHA256 均为：
`394e22e11d6dc9874d6d28728741b7169765c6d1eae32f9dce9582d40a912597`。
逐文件不匹配、额外/缺失冻结文件、应删除但仍存在文件均为 0。本轮只写本 output 与 `apps/video-clipper/.runtime/performance-baseline/acceptance/r2-verifier/`，没有改产品、报告、标准、索引或原始证据，没有提交、推送、鉴权或采样。

## 本轮新执行的核查

### 第一轮到第二轮的改动范围

冻结文件仅有四处内容变化，未增删冻结文件：

1. `docs/ai/performance-baseline/controller/python_profiles.py`：计数属性、分母属性及解释改成可见口径。
2. `apps/video-clipper/reports/performance-baseline/python-summary.json`：由原 SVG 重算的精简投影。
3. `apps/video-clipper/reports/performance-baseline/evidence-index.json`：同步新摘要 SHA 引用。
4. `apps/video-clipper/reports/performance-baseline.md`：修正具体样本和语言建议的解释。

三份 runtime Python summary 是允许更新的派生产物，原 SVG/log、正式计时和原生数据不属于本轮修改。`freeze-start.json`、`freeze-end.json` 保存独立冻结记录。

### Python 计数口径与真实重算

逐行审查当前公共摘要工具，确认没有保留 `self_samples` 等误导兼容别名。残余仍由可见父区间减可见直接子区间并集计算，现名 `visible_residual_samples`；分母名为 `visible_recognize_entry_union_samples`，识别覆盖属性和具体函数投影均同步改名。

工具及报告正确说明：Inferno 的 0.1% 绘图阈值省略窄帧；单可见节点残余是该节点自身驻留的上界，按函数聚合还会遗漏该函数窄出现，因此不是完整函数上界；inclusive 只覆盖可见出现；识别分母只是可见入口区间并集。残余和 inclusive 均不能当纯解释器 CPU 或由 sample/rate 推墙钟。interpolate 的 2115 和 people_flush 的 4914 已明确为聚合可见残余，没有继续称精确 self。

用项目绝对 `.venv/bin/python` 独立执行当前公共工具，从原 SVG/log 重算 A/C/D；仅在内存中调整输出路径到自己的 `acceptance/r2-verifier/python-analysis/`，没有修改源码或覆盖现行及首轮证据。结果如下：

| 场景 | SVG / 日志样本 | 采样错误 | 可见识别入口并集 | 可见残余 | 状态 |
| --- | --- | ---: | ---: | ---: | --- |
| A | 17508 / 17532 | 0 | 4210 | 1 | passed |
| C | 22631 / 22667 | 2 | 12179 | 75 | passed_with_sampling_errors |
| D | 46137 / 46153 | 0 | 32199 | 136 | passed |

A 握手样本仍为 10427，与可见识别入口区间无重叠。三 SVG/log 原 SHA 全部与首轮自有摘要相同。对首轮独立重算结果逐字段递归映射必要改名，并排除此次新增/修正的解释字符串后，A/C/D 所有数据完全相等；没有数字变化。当前三 runtime summary 与本轮新算结果逐字段完全相等，report Python summary 的全部投影字段也与本轮结果相等，三个 source_summary 路径/大小/SHA 均匹配。证据：`python-comparison.json` 及自有 `python-analysis/{A,C,D}/summary.json`。

因此第一轮 P2 已用最小范围修正闭环；原始 SVG 无法恢复精确 self 的事实得到保留，没有为保留旧说法而改变实测或放宽数据判断。

### 原始证据不变与引用

本轮重新计算十成片 SHA，均与首轮独立完整解码校验的实际 SHA/大小相同；重新计算六输入视频及三权重 SHA，也与首轮一致。147 产品实现、配置和测试文件与首轮冻结完全相等。三 SVG/log 已随真实重算再次计算 SHA。

核对当前索引中的 132 个 SHA 引用记录，无不匹配；大 raw 文件没有重复全量 hash。四 raw trace 的索引 manifest SHA、文件路径/大小清单一致，raw 文件均无首轮冻结之后的 mtime，原生精简摘要和原始索引仍匹配。人类报告的当前本地链接全部可达，没有引用其他角色通信目录。当前正文仍标待独立验收，evidence-index 的 independent_acceptance 仍为 pending，没有先行写通过。

证据：`evidence-invariance-and-index.json`。本轮大 trace 未重复全量读取或重导出，这一点不冒称已执行；其内容判断沿用首轮实际 XML 重算及本轮索引/文件不变核查。

### 聚焦检查

- 当前 Python 摘要工具语法检查通过。
- 四个本轮修改文件的行尾空白检查通过。
- `git diff --check` 首尾均通过。
- 定向检查当前工具、三 runtime summary、人类报告、Python 精简摘要和索引，无旧 self_samples/self_percent/完整识别分母别名残留；历史首轮通信和诊断没有按当前代码对待。

证据：`static-checks.json`。此次只改派生计数名称、解释和引用，没有产品/前端/公开契约或数值计算改变；原图真实重算与逐字段比较是本轮必要的聚焦验证，不重复产品测试。

## 沿用首轮独立证据的结论

- 真实 HTTP/WS 会话、独立 worker、recognize/render、失败归档和互斥统计实现已在首轮审查，147 产品文件本轮不变，结论沿用。
- 首轮十输出 FFmpeg 完整 AV 解码、PyAV 帧/PTS/音轨、计时与声明区间和、三短 ON/OFF 及 A 补录严格等价全部通过；本轮视频 SHA 未变，沿用，不重复解码。
- 首轮 103 后端测试/5 合成控制检查、输入来源映射和连续性、六正式资源检查通过；本轮不重复执行。精确 pnpm 包装器未在首轮/本轮重新执行，首轮已按允许的项目 Python 入口运行同源 pytest，未安装或绕过供应链策略。
- 首轮 A 全段及 C/D 三窗口的三类原 XML 全部独立重解析，另独立解析 CNN 探针，确认 CPU/GPU/MPS 主窗和尾部限制足以支持限定热点建议；本轮相关原始索引、摘要和文件清单不变，沿用。C 两次 Python 展开错误、0.1 秒 ready 观察边界及 signpost 尾部限制仍保留，没有外推全段 GPU 利用率。
- 原生叶库/叶符号与有限语言建议互证，Python 可见计数修正不改变 D CPU 姿态、前处理与模型调用优先方向；没有宣称全模块改 C++/Rust 已有实测收益。

首轮证据见 `verifier/output.md` 和 `acceptance/r1-verifier/`。本轮只复验已确认的唯一修正，没有新模型处理、录制或权限操作。

## 交付边界

本轮无剩余必修问题，可以由主控做已约定的工作流状态收尾；收尾若仅更新报告/README/路线图/索引的验收标记，仍按输入要求交我检查该差异。当前本轮通过不等于已提交、已推送或已集成到 develop。
