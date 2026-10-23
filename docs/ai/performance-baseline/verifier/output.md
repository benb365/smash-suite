# 独立验收第一轮结果

## 结论与冻结版本

- 轮次：1；版本：`r1-20261021-final`。
- 整体：**不通过，需修正一处 Python 剖析摘要的语义后重新冻结复验。**
- 功能：**真实测量、识别导出、统计 ON/OFF 等价与原始采样证据通过本任务限定范围的检查**。不代表准确率、浏览器、重新打包或 30 分钟产品验收。
- 代码：**不通过**。产品路径与测试通过；公共 Python 摘要工具把经过省略的 SVG 可见残余当作精确 self 样本，见下方 P2。
- 文档：**不通过**。报告把上述数值定义成“最末 Python 帧”，并称分母为完整识别子树，超出了 SVG 能证明的口径。其余主要计时、资源、原生窗口和语言建议与证据相符。

验收开始及结束均独立复算 402 个冻结文件，实际树 SHA256：
`f17a09efbd093a4a3a303960d2d407495c1667e08d990138f83413ab42484edc`。
逐文件差异、额外/缺失冻结文件及应删除但仍存在的文件均为 0。分支 `codex/performance-baseline`，HEAD `979caeb1cefedd78b2cebac52ca38f28a84d7563`。本轮未改实现、报告、标准或原证据，未暂存/提交。

本轮自有证据目录：`apps/video-clipper/.runtime/performance-baseline/acceptance/r1-verifier/`。以下路径均相对此目录；工作树根为 `/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite`。

## 必须修正的问题

### P2：省略过窄子帧的 SVG 无法恢复精确 Python self

位置：`docs/ai/performance-baseline/controller/python_profiles.py:114–116,144–159,230–231,313–317`；`apps/video-clipper/reports/performance-baseline.md:111–117,121,148`；受影响产物包括 `reports/performance-baseline/python-summary.json` 中 self 字段及相关解释。

工具从 SVG 父区间减去可见直接子区间，输出 `self_samples`。独立核查 [py-spy v0.4.2 源码](https://raw.githubusercontent.com/benfred/py-spy/v0.4.2/src/flamegraph.rs) 确认 `opts.min_width = 0.1`；[Inferno 的绘图实现](https://raw.githubusercontent.com/jonhoo/inferno/main/src/flamegraph/mod.rs) 在输出 SVG 前裁掉过窄帧。当前三个原始 SVG 的最小可见宽度恰为 18、23、47 样本，对应总样本 17508、22631、46137 的 0.1% 阈值向上取整。可见父区间的残余因此可能包括被省略的子调用，不能严格称为原始栈的最末 Python 帧。

对于一个可见节点，此残余是该节点真实 self 的上界；聚合到函数时还会遗漏该函数自身被省略的窄出现，不能把聚合数简单视为完整函数 self 上界。按函数寻找识别入口的分母也只能保证是可见入口区间并集，无法由该 SVG 单独证明所有窄出现均已包含。报告目前把 A/C/D 的 1/75/136 及 interpolate、people_flush 等 residual 直接标 self，并称分母完整，缺少这一限制。`svg-self-semantics.json` 保存原图重算证据。

影响：会夸大对具体 Python 叶调用的定位精度。此问题不推翻六正式墙钟、十成片、ON/OFF 区间等价、A 等待区间与主要识别入口不重叠，也不推翻有原生证据互证的缩放、CPU 姿态等方向；不能据这些 residual 判断解释器成本。

建议最小修正：保留已有原图与数值，明确改成“SVG 可见残余”，说明省略阈值、潜在遗漏及分母为可见识别入口并集，同步工具字段/解释及报告相关自述，避免称精确 self。若坚持提供精确 self，则必须有未裁剪原始栈支持，现有 SVG 不能补出；本轮未启动补采。修正后重新冻结，针对摘要、引用与报告复验，不需要为了措辞修正重复十次模型处理。

## 已独立执行的功能与一致性检查

1. **十输出校验完成，0 issue。** 审查公共 `controller/validate_outputs.py` 后实际执行相同检查。仅在内存中将其新日志目录从 `output-validation/run-*` 改至获准的本验收目录，源码、断言、输入读取均未变。结果：`output-validation/run-20261021T031341Z/validation.json`。
   - 十视频 SHA 与 runner 一致；FFmpeg 完整 AV 解码 exit 0；PyAV 实际帧、尺寸、单调 PTS 和音轨均有效。
   - 六正式 balanced/MPS 与有效统计满足要求；三产品阶段和等于总耗时；worker 声明时长等于导出区间之和。
   - 三份统计 ON/OFF 对照和 A 补录对照的原始 predictions、export_ranges、帧数和音视频结构严格相等。
   - 十份原始资源均观察到后端、worker 和 FFmpeg。A 首视频 PTS 20ms 与容器/视频流时长差异保留，没有按声明时长误判丢帧。
2. **输入/模型/配置/实现冻结核对通过。** 实际重算六输入视频与三权重 SHA；report inputs 与 runtime media inputs 对象相同；147 实现、配置及测试文件与测量前 freeze 和五份运行 manifest 相等，profiles/selection/FFmpeg SHA 相等。证据：`freeze-inputs-environment.json`。
   - 原始 EOF 统计逐项等于声明帧数；来源逐帧像素/PTS 映射、音视频包映射、连续性 JSON/接触表实际存在。成功的 FFmpeg error 级别日志多数为 0 字节，这是无错误输出，非伪造非空日志要求；退出码及非空 preflight 汇总均保留。
   - 长片 requested、实际包窗口、decoded_frame_pts 分别保留，未擅自改成整秒。独立查看 C-long 接触表，符合固定机位抽样范围；没有把抽样当逐帧人审。
3. **六正式原始计时/资源复核通过。** 总秒数分别 48.054031875、247.772215541、137.166507625、585.813914958、335.083100833、884.157396750。主阶段互斥，未分摊均为正；全部外部读取错误 0。C-long MPS 恰有四个 >1.5 秒缺口，其余无此缺口。证据：`formal-resource-check.json`。查看 C-long 资源图确认断线/灰条、阶段分界、MPS 不延伸成片、RSS 与 MPS 分列可读。
4. **Python 原始 SVG/log 重新解析完成。** `python-results.json` 与 `python-analysis/{A,C,D}/summary.json` 保留本轮结果；A/C/D SVG 17508/22631/46137、日志 17532/22667/46153、错误 0/2/0；可见 recognize 并集 4210/12179/32199，A 握手 10427 与识别区间无重叠。三个 invalid-format 警告及 C 展开失败均保留。C 的局部缺失不要求整次采样失效，现有大段入口覆盖与原生阶段证据足以支持有限方向建议；没有据采样率推墙钟或宣称原生逐时刻补齐缺样。上述 P2 限制精确 self/完整分母表述。

## 原生证据的独立判断

对 A 全段及 C/D 三窗口的**既有三类原 XML 全部重新解析**，未启动 xctrace 导出或采样。`native-reparse.log`、`native-*-{time-profile,metal-gpu-intervals,os-signpost}.json`、`native-reparse.json` 保存原始计算结果。

- A：目标 PID 42952/UID501；与 Python PID38406 为不同捕获。识别 CPU 56257 样本/56.257 累计权重秒，Metal Active 并集 21.873284 秒，MPS 170595 事件均复现。当前解析器对 A 比历史 summary 多出配对/全原始范围字段；新增值不是原证据冲突。独立核查 CPU 完整原始范围 0.692955875–49.103954833 秒也落在 TOC 49.104748 秒内。
- C observation、D observation、D pose 的 ready/TOC/识别时钟映射及 stage 验证均完整复现。主窗分别 7.950527191、7.944506884、7.913005829 秒；CPU 样本/权重 10411/10.411、9559/9.559、10245/10.245；Metal 全局并集 4.634414、2.661880、0 秒；MPS 窗内事件 65855、49367、0，配对裁剪并集 5.652257、3.538855、0 秒。没有把线程累计权重当墙钟，也没有把嵌套 GPU 区间相加。
- 所有窗口引用与重复定义诊断为 0。CPU 结果对象逐字比较中的差异来自 set 迭代导致的等权 inclusive/native-example 排名顺序，以及 top50 截点处等权条目取舍（C 两个 PyAV 调用、D pose 两个 OpenMP 调用）。排除这两个由集合产生的排名字段后，其余 CPU 字段完全相等，主要叶库/叶符号权重、计数、原始时间范围与诊断均一致；详见 `native-rank-ties.json`。A 的新解析还增加只读诊断字段，已单独辨明，不把 `equal_full_analysis=false` 直接当失败。
- C/D signpost 尾部 0.559534833/0.549399875 秒从原 XML 复现，确含 Begin/Event/End 和 MPSGraph。又独立解析先行 CNN 探针原 XML，TOC 7.890086 秒、signpost 结束 8.458859166 秒、尾部 0.568773166 秒；CPU/GPU 仍在 TOC 内。证据：`native-boundary-check.json`。内部停止机制未证实，但该跨表尾部现象得到独立探针复现，主分析保守裁掉尾部、时钟未平移、stage 及 CPU/GPU 原点严格匹配，足以支持报告限定的阶段热点方向；不支持全段 GPU 利用率或无异常全覆盖。这不是本轮阻塞。
- D pose 的目标 Metal/MPS 为 0，与 `modules/models/keypoint_rcnn/__init__.py` 的 CPU load、CPU tensor 和模型调用互证；libBLAS/PyTorch/torchvision 原生叶权重与图一致。

`artifact-links.json` 独立核对 129 个 SHA 引用记录，未发现不匹配。四个 raw trace 的文件数/路径/大小与保存索引一致，分别 500/457/451/431；大 raw 文件未重复全量 hash。报告当前引用可达；扫描发现的旧 backup 记录和原数据相对链接缺失为该 linked worktree 既有本地布局，不是本次新增报告断链。`failure-evidence-check.json` 确认 A 无效大 trace 已按清单删除、inventory SHA 正确、失败日志与有效 raw 均保留。

## 代码、测试和文档检查

阅读新增未跟踪 benchmark、statistics、测试及全部产品/算法差异。runner 确实走 HTTP 导入/run/query、WS 续租、新后端与新 worker、真实 recognize/render，归档后才清理；没有缓存替代推理。统计只记录计时/计数/资源，不改变配置或区间，禁用时不输出假统计。互斥阶段与嵌套子项实现符合当前口径；失败证据保存有独立合成测试覆盖。删除只涉及旧缓存独占清单/入口/打包数据项，未删流式 replay_frames 或合成测试。前端和公开状态契约无变更。

独立运行：

| 检查 | 结果 | 日志 |
| --- | --- | --- |
| 项目绝对 `.venv/bin/python -m pytest`，关闭 pytest/bytecode 缓存并将临时目录限定在验收目录 | 103 passed，1 个 Starlette/httpx 既有弃用警告，9.95s | `pytest.log` |
| 公共 `controller/profile_logic_checks.py` | 5 passed，纯合成控制逻辑 | `profile-logic.log` |
| Python 源码 AST 语法检查 | 93 文件，0 错误 | `static-checks.json` |
| 新增/修改文本行尾空白及 `git diff --check` | 0 问题，末尾再次通过 | `static-checks.json`、`freeze-end.json` |

精确 `pnpm run test:backend` 包装器**本轮未执行**，以免触发此前记录的包管理器自动安装/最小发布时间限制；已读 package.json 确认实际脚本就是 `.venv/bin/python -m pytest` 并独立完成同源测试。没有安装、下载或放松策略。本轮没有重现此前包装器拦截，不能把旧拦截写成此次实测。

未执行：前端检查（无前端/公开契约修改）、新一轮正式模型测量/采样/鉴权、重新打包、完整浏览器交互、准确率或旧 16 例缓存回放、30 分钟产品验收。后四者不是本任务用户确认的完成标准，未冒称完成。

文档主要性能数值和优化上限与原证据一致；D 姿态入口、第二遍解码、C 整个人轨迹阶段上界未重叠相加，C++/Rust 建议没有把原生计算算成 Python 重写收益。资源/原生图清晰。阻塞仅为上方 P2 的 Python 剖析计数口径，修正后再交独立复验；本轮不应更新为已完成或提交。
