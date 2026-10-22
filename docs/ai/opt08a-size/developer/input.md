# 第1轮开发：尺寸实验入口

只在本worktree执行，先读task.md、根README和对应TrackNet/rally README；不读任何verifier目录。只写自己的output、docs/ai/opt08a-size脚本与定向检查、该任务正式报告；不改生产或07A脚本。不运行模型/视频，由主控在06独立复核结束后串行执行。准备branch codex/opt08a-size（当前detached develop4910e1e，先检查status；不回退已有修改），比对主pyproject再复用主.venv链接，不安装依赖。

实现最少实验runner run.py：--size 288x512|216x384|144x256、--case A-short（后续需要可复用C-short但不先跑）、--inputs、--models、--output；每次只一变体。复用已有docs/ai/opt07a/recognition.py（可importlib加载其main、load_reference/ProcessSampler等），不要复制200行runner，也不要改其源文件。其main在import recognize前动态绑定TrackNet package，注意实验源必须在此时绑定；不要让helper后续baseline load覆盖掉候选。保留全部真实路径/输入/权重/MPS检查、完整recognize、统计/结果和失败落盘；最终报告variant/size/实际派生类来源不能冒称原版。

源为本worktree当前modules/models/tracknet/predictor.py，派生只改resize参数与输出points坐标比例；每个文本替换assert恰好1次，记录原始/派生源码SHA、配置、派生代码可恢复（保存源码到本任务.runtime或保存精确替换规则足够）、runnerSHA。坐标映射用heatmap.shape[1]/[0]，288应严格不变。加载为modules.models.tracknet下独立模块以支持相对import，实际绑定到recognize.TrackNetPredictor可核对；物理生产文件哈希不得代替派生类SHA。

模型每次三帧调用points可在轻量子类wrapper中记录调用序号、输入帧数、points x/y/confidence，调用顺序对应原生分组；A4200点元数据内存足够，不留整片图像。C若缓存传frame_ids也应透明保留。三种变体都同记录成本；统计复用已有helper，写盘在识别墙钟外需明确，不把它隐藏称产品总成本。无需保存巨大heatmap数组。

定向检查应验证源码唯一替换/三合法尺寸、热图大小映射（可提取最少纯函数或检查执行派生__call__的stub模型以验证实际映射，不写仅镜像字符串测试），288与原版预处理/解码路径等值；不跑真实torch模型或媒体。可以使用CPU合成小图和stub model验证，不算实际效果。不要额外泛化框架、生产参数或下载；未知点不能静默兼容，明确失败。

output.md 写第1轮、实现文件SHA、使用方式、已运行检查和未跑模型事实。完成入口与检查后暂停；不要先写虚构正式实验结论，不暂存提交。

## 第1轮实际结果与报告收口

主控已串行完成三份A完整识别，运行在apps/video-clipper/.runtime/opt08a-size/A-short-{288x512,216x384,144x256}；每份run/result/statistics/resources/derived_predictor真实存在。控制29.9666052079s、216为22.0375244580s、144为19.7120881672s，均1400调用4200帧。请从实际JSON重算，不手抄全部。

主控取舍：两候选本轮不采用，不补C，不改产品。216原始第三段56.72→56.64少80ms，第一段9.60→15.40多5800ms；144原始并集相对控制共少880ms（逐段缺口应独立算并保留），还有额外保留。控制raw/export应与07A已集成候选保存结果完全一致。当前没有匹配人工标签，因此不能声称这些差异就是人工真值漏球或准确率不合格；只能说输出改变、尚无法证明效果保持，按已约定保守门槛不保留。没有证据不得把80ms称为允许误差，也不因单次快而放宽门槛。结论仅两种尺寸/当前A试验，不否定其它尺寸或重训练方向。

主控已按review-video-results skill准备modules/models/tracknet/.runtime/opt08a-size-review.json（首PTS91ms/真实168s/三算法行、无truth），启动http://127.0.0.1:57088/并实播8→17秒，时间轴同步。在13.022秒截图见主目录apps/video-clipper/.runtime/opt08a-size/viewer.png：两球员在场上走动等待，中档保留、原尺寸/小档删除；该视觉观察仅定位新增保留风险，不是人工标注或完整回合边界审核。不要修改图片或造绿色标注。

完成：新增一个简短summarize.py（或一次性确定性命令，最少代码）按同一raw/export区间并集计算逐段missing/extra，输出正式apps/video-clipper/reports/opt08a-size/summary.json；记录每帧points相对控制差异数量/坐标差统计、工作量、耗时/资源观测、版本/环境/哈希与原始证据路径。不得把这些诊断统计冒充精确效果或稳定速度；资源沿用真实samples注明1秒采样。需确认控制和07A保存raw/export一致，所有派生SHA、实际类/输入尺寸/EOF均可追溯。

正式目录README.md先结论和范围，简洁表格尺寸/单次时间/输出差异，逐段失败例/数据链接；必要run/result/statistics/resources与派生源码保留.runtime，正式summary不可仅布尔值。复制查看器JSON到正式报告review.json方便复看，保留原绝对媒体路径，不生成HTML；复制主目录截图为正式viewer.png，逐字节，报告写清视觉范围。

更新自己的output和主控task当前状态（由主控审核）为本轮实验完成、两候选不采用、待独立验收。删run.py无用os/types imports即可（注意此源码改动虽不改变派生source，会使旧run记录runnerSHA为历史入口；须记录旧SHA与当前纯import清理差异，不为它重跑模型）。如为最小改动也可保留两个unused import等最终审查再判断，不需重复运行。

不改已有运行JSON/07A代码/生产实现；不要再跑视频或模型。完成必要定向检查、diff check后暂停，等待冻结。

### 冻结前主控复核的最小修订

README“**三种尺寸**的4200个球点都至少字段不同于288”应为“**两种缩小尺寸各自**的4200个点”；控制与自己没有差异。报告及summary关于截图范围应精确写“查看器实际播放8→17秒，截图保存13.022秒这一时点；未逐帧审核/人工标注”，不能称单张截图覆盖8–17秒。summary limitations第一项baseline应指本轮新288完整控制（其raw/export与保存07A候选相同），不能把当前耗时误归旧baseline。请检查resource phase_seconds实际统计键与真实JSON相同，修正若取空键；保留真实证据，不重跑模型。上述是报告事实修正，其它范围不变。
