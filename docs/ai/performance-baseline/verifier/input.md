# 独立验收第一轮

## 独立上下文与冻结版本
你是全新独立验收角色。只在 /Users/bytedance/.codex/worktrees/performance-baseline/smash-suite 工作；先读根AGENTS、README与相关应用/模块规范及 task.md 的当前用户授权。不要读取本任务developer/、media/、continuity/、replay/、validation/、profile-analysis/任何input/output通信；当前公共工具已集中controller/。不要依赖主控/开发“通过”文字，按实际实现和原始证据独立判断。只写 verifier/output.md，可在应用.runtime/performance-baseline/acceptance/生成自己的日志/临时检查数据；不得改源码、报告、标准、现有证据、索引或暂存/提交。没有其他角色继续写实现，主控也停止写冻结文件。

版本：r1-20261021-final。精确提交/分支/文件SHA与删除项见 ../controller/acceptance-freeze-r1.json。先独立复算其中所有内容（不读角色通信），不符停止并回报。验收最后再次核对未变化。输出必须标本轮、版本、实际复算SHA；过期或只启动不能判通过。

## 用户确认范围
6份A/C/D短长输入各1次正式完整真实识别+默认balanced导出，另3短完整Python采样并stats OFF对照，A原生因首次保存失败另补一次完整处理，共10实际输出（不是只有9）。A/C长约15min，D约611s；每种仅一次，不推稳定波动/复杂度、不替代30min产品验收。工具py-spy0.4.2+Instruments，用户后来明确同意C/D原生按主要阶段5–10秒短窗口，Python仍全段；A已保存全程原生直接复用。普通UID501应用，只有py-spy采样器管理员附加；此次验收不得启动新鉴权、采样器/模型或重跑正式测量。

旧16例回放依赖35缺失观测，用户明确批准由三短真实ON/OFF代替并删掉无用独占入口；必须验证新标准，不再要求补旧缓存，也不能称旧16例通过。旧C2=8/D2=14与当前9/13媒体SHA/路径/音轨、缓存路径不同，已比较参数相同但因果未定位；不继承历史准确率。公共事实与原始历史报告链接在controller/state.md。这里不是许可忽略当前同输入ON/OFF的差异。

## 功能、代码、文档分别给结论
1. 真实路径：benchmark应复用应用HTTP/WS lease、新worker、真实recognize/render，不伪造、缓存代推理或改公开API。六正式含正常加载/校验不含下载/上传/手动保存；统计主阶段互斥，嵌套/并行子项不相加。统计开关不改参数/回合/导出区间。核对新增和未跟踪源码，不只看git diff--stat（未跟踪内容尚未暂存）。检查失败证据保存和采样覆盖。
2. 现有原始输入/权重/配置/代码一致性：report asset inputs.json与baseline manifest、pre-measurement-freeze等；当前147实现/配置/测试文件与5份运行manifest共同文件相等，不要求报告生成后的全树hash完全相同。输入AV解码/Source EOF/源像素时间校验/画面连续性证据在应用runtime/media/，需要核实实际非空，不用历史backup作当前证据。长片streamcopy实际keyframe窗口、帧数/时长/PTS/court与原意的差异已冻结，不擅自改回整秒。
3. 输出：独立重跑公共controller/validate_outputs.py（必须项目绝对 .venv/bin/python、普通本机权限）。它应校验10视频SHA、FFmpeg完整AV解码、PyAV帧数/尺寸/PTS/音轨、产品计时及声明区间和、6正式有效MPS统计、后端/worker/FFmpeg资源覆盖，3原对照+A补录都严格等价。主控已有结果在 app.runtime/output-validation/run-20261021T024238Z/validation.json，不能只抄结论；审查检查实现并自己运行。实际A输出stream start0.02s、duration比容器少0.02s，不能把worker声明时长等同媒体各口径，也不能把真实起点偏移误判为丢帧。六组资源曲线保留C-long MPS4个>1.5s缺口，RSS/MPS不相加、峰值是观测值。
4. Python：原始SVG/log在profile-control-{A,C,D}。public controller/python_profiles.py及报告摘要用于检查；可读原图，不覆盖旧summary。A SVG17508/log17532/0errors，C22631/22667/2errors，D46137/46153/0errors；SVG各有1条ignored-invalid-format提示。A睡眠worker.py:52驻留10427单列，recognize4210，与等待互斥；C recognize12179，D32199。C两次栈展开失败原因未证实，状态passed_with_sampling_errors；不得把缺失说成0或由sample/rate推墙钟。你须独立判断实际识别覆盖与其他证据是否足够支持有限结论，不能因主控状态文字直接通过。
5. 原生：A来自两次独立捕获，Python PID38406与native PID42952不同、原生额外补录已单列。A有效summary在app.runtime/profile-analysis/A/full-native-A-parse1，索引引用首次成功XML/raw trace；首轮不可导出9.7GB和重复partial122MB已保存SHA清单/失败日志后清理（controller/cleanup.json），有效raw均在。
C/D最终有效候选目录app.runtime/profile-analysis/{C,D}/phase-windows-final-v2，C observation、D observation+pose；各summary/index。原始trace保存码0，CPU/GPU目标PID过滤、id/ref无未解析/重复，主要分析取实际ready→TOC∩识别约7.95/7.94/7.91秒；完整TOC13.046/9.190/8.956秒含附加。0.1s轮询ready边界限制要明确。CPU跨线程累计weight非墙钟，GPU Active须全局并集，不能加嵌套区间；MPS paired union须裁剪，不当GPU利用率。Dpose CPU有效、目标Metal/MPS为0，与源码CPU模型路径应互证。
C/D observation signpost表全范围尾部超过TOC0.559535/0.549400秒，包含Begin/Event/End，不能说仅异步End。先行受控CNN工具探针也有0.568773秒尾部，证据app.runtime/cnn-window-probe/stop-boundary-check.json及其原XML。工具采用passed_with_signpost_tail，CPU/GPU原点严格核对完整raw范围；不改offset/扩大容差，MPS主统计排除窗外，full表尾部原样保留。xctrace内部具体停止机制未证实。**你应独立核查这一数据边界解释及保留的原始表/配对/时钟/stage证据，判断它是否足以支撑报告中的限定热点结论。不能强制通过，也不能仅因额外的“所有表必须完全落在TOC内”假设机械判失败；有实质未解释异常或必要证据不足则明确不通过并说明具体缺口。**无需重导出/重复hash大文件；可独立校对索引并抽查/计算实际原XML或区间并集。
6. 语言建议：只评估实测Python热点；Python self/原生调用驻留不等于解释器CPU；PyTorch/OpenCV/FFmpeg已原生，整段改C++/Rust无证据收益。D姿态入口约占长片49.9%，第二遍解码转换5.23%，C人轨迹整个阶段3.56%，上限不能重叠相加。报告每方向应有证据、耗时/资源口径、措施、理想收益上限或无法量化边界、复测办法，不把剖析时长当正式基线。看图表是否可读、引用SHA/路径是否可达、阶段native窗口不外推整段GPU利用率。

## 独立执行检查
先读package.json后端脚本与pytest配置。原指定pnpm run test:backend曾被pnpm12.6自动安装的供应链最小发布时间策略阻止（watchpack@2.6.3），没有放松策略/改lock。你可核实当前命令；不要下载/安装/修改环境来绕过，必要时用项目绝对 .venv/bin/python -m pytest 执行同一实际测试脚本，按事实报告包装器与实际测试分别情况。此前同源全量103 passed/1既有Starlette警告；一次已有realtime overload时序测试process_s=0，单项和同源全量复跑通过；本轮若失败须独立核实，不用旧通过掩盖。
独立执行controller/profile_logic_checks.py（5项合成控制逻辑，无真实进程/授权），git diff --check及新增文件空白/语法检查。前端/公开契约未改则无需前端测试。适当查看真实资源/Native图；可直接view_image。实测已完成且有完整证据，无疑点不要重跑10次模型。

## 输出与结束
verifier/output.md区分功能、代码、文档三个结论，给本轮版本/检查日志路径、必要风险/阻塞与整体是否通过。若发现问题，只报告精确文件/行/影响及建议，不修实现或放宽标准。记录所有未执行项，不把启动、摘要status或模型代码存在当完成。验收通过后主控才会更新工作流状态并本地提交，保持worktree、不推送不集成；develop仍进行中。

## 验收中的补充核对线索（不改冻结实现）
主控核对官方py-spy v0.4.2的src/flamegraph.rs时看到opts.min_width=0.1（https://raw.githubusercontent.com/benfred/py-spy/v0.4.2/src/flamegraph.rs 第76–82行）。当前Python摘要从SVG可见直接子区间扣除推self_samples；若Inferno会省略窄于阈值的子帧，该self可能包含被省略的子调用，不能严格等同完整原始栈的最末Python帧。请独立审查这一语义和报告/脚本说明是否准确，以及是否影响本轮限定结论；有问题按缺陷报告，不修改文件。主控未更改任何冻结文件，也未据此推翻现有模型/区间数据。
