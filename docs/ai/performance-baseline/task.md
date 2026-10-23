# 性能基线与优化诊断
## 授权与状态
用户2026-10-20已确认完整方案并要求实施。使用根AGENTS与run-task-workflow，不重复询问已授权方案。本任务worktree=/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite，分支codex/performance-baseline，基线979caeb1cefedd78b2cebac52ca38f28a84d7563，已完成并经用户确认于2026-10-21集成develop，主控/root。原目录/Users/bytedance/workspace/experiments/smash-suite仅更新认领；原outputs/不读写暂存。开发/媒体/验收角色仅读task、自身通信目录、必要实现需求和主控批准证据，不读其他角色通信。
## 确认范围
当前源码A/C/D各短长共6正式处理各1次，另3短各1剖析，共9次真实完整识别导出。A/C长900s，D约611s；单次不推断稳定波动，不替代30分钟验收。默认balanced/现有算法模型采样线程、自动设备(正常本机MPS已确认True)，不优化或改语言、不打包。新会话新worker顺序执行；权重预先准备，计时含正常校验加载，不含下载/导入/手动保存。原有回放不能冒充真实推理。
短输入(原目录datasets/badminton-v1/local/rally/)：A1=m1-short-a1-01-20261015/clip.mp4；C2=personal-qianfoshan-singles-restored/clip.mp4；D2=d2-check-20261018/clip.mp4。长源(原目录datasets/badminton-v1/local/source-videos/)：A1/source.mp4 [600,1500)，C1/source.mp4 [120,1020)，D1/source.mp4 [0,610.946)。媒体角色在worktree忽略目录新建streamcopy长片，保持音轨/PTS/尺寸/帧率；完成实际源映射、像素/时间校验、全音视频解码、FileFrameSource EOF和画面连续性检查后方可推理。无效输入保留诊断并暂停，不拼接补帧/换源凑数。不同短长来源不证明复杂度。
批准媒体证据索引：apps/video-clipper/.runtime/performance-baseline/media/inputs.json，六项case_id A-short/A-long/C-short/C-long/D-short/D-long，scene high/courtside/personal、video绝对路径、court默认null、SHA/实际元数据/预检证据及状态。
## 实现与统计
复用真实产品API/会话续租/独立worker/FFmpeg；会话清理前归档证据。公开HTTP/JobState/前端不变；新增应用所属benchmark runner和可选内部统计，从worker传collector到recognize，统计开关不改算法结果。
复用准备/识别/成片/总monotonic墙钟；识别拆模型初始化、视频观测、人物/轨迹、动作分析、回合判断、中间写盘。已有TrackNet preprocess/inference+transfer/point decode、FileFrameSource decode/conversion复用；主阶段互斥，嵌套/并行子项不能相加重复计费。
计数帧/解码遍数、模型调用/人物裁剪、候选轨迹等。每秒采后端+递归worker/FFmpeg CPU、RSS、工作目录含源/不含源占用、磁盘剩余；worker内MPS allocated/driver。留PID覆盖、采样时刻间隔缺口，观测峰值不称精确峰值，统一内存口径不相加。无庞大逐帧日志/一般化插件框架/兼容猜测。
冻结源码提交与工作树SHA、算法配置、依赖/FFmpeg/输入/权重SHA/court。
## 剖析
3短片独立剖析，不把剖析耗时作基线。用户已选择py-spy0.4.2(有arm64 wheel)+Instruments CPU原生/Metal时间线/MPS signpost。管理员只用于采样器，被测app普通用户。先数秒探针验证附加/录制/导出。py-spy目前未安装，Mac不支持native栈，Python栈驻留不能算纯CPU计算。xctrace已确认模板Metal System Trace/Time Profiler和instrument Time Profiler/os_signpost；组合尚未实际跑。torch2.8通用profiler无MPS，独立torch.mps.profiler.profile(mode="interval,event",wait_until_completed=False)可signpost。不要强制每算子同步。
主控负责工具预检，批准证据将写controller/profiler/；角色可读该证据。工具权限失败停对应步骤明确回报，不绕保护、不替换CPU或虚称完成。
## 报告与验收
方向：模型加载/预处理/传输；D重复解码/CPU姿态/逐人裁剪；C候选扩展匹配；整片观测内存；编码/读写。每项证据、占比、措施、收益上限、验证方式，区分支持/假设。C++Rust只评估已证实Python热点及跨语言转换/维护成本，不把底层原生模型归给Python重写收益。
正式报告JSON/图表/证据索引归apps/video-clipper/reports；大trace/视频/逐秒数据归其.runtime并保存SHA，不能只引用易失/tmp。执行流水在本docs/ai，更新应用入口/路线图。
必要pnpm run test:backend、三短真实统计开关对照、git diff --check；有意义的统计开关等价、进程树覆盖、计时/失败保存测试与真实输出检查。六组识别导出均完成且三剖析有效才能通过。冻结后独立验收功能/代码/文档；验收期间停止开发，后续实现修改必须复验。通过后本地提交保留worktree，不推送不合入，等待用户集成确认。develop保持进行中。
## 主控确定的共享媒体索引契约（第一轮）
inputs.json 顶层为 {"cases":[...]}，每项固定包含 case_id, scene, video(绝对路径), court(null或已确认四角), sha256(文件SHA256), status("passed"只在全部必要预检通过后)。额外元数据和证据字段自由附在项内，runner应保存整项以保留来源，不将未预检输入送推理。六个case_id使用A-short/A-long/C-short/C-long/D-short/D-long。媒体内容问题/预检失败项status为failed或blocked并记录reason，不能视为passed。

## 用户后续确认（覆盖旧缓存验收要求）
用户已明确回复“基本同意推荐处理，没有用的历史中间数据就删了，不要有冗余残留”。本轮以三段真实短片的统计开启/关闭对照替代依赖35份缺失观测的16例历史回放。6正式保持统计开启；3短剖析关闭聚合统计、保留profile握手和MPS signposts，比较每类原始predictions和export_ranges及输出结构/帧数。仍总计9次完整真实处理。旧数据缺失事实保留，不称旧16例通过。
仅清理这条旧检查独占且已失效的 active cases.json/replay.py/打包数据项及当前入口引用；原始视频、标注、模型、当前算法证据和有用的stream replay_frames/合成单测保留。历史docs/ai执行证据和backup归档不做全库清理。删除内容仍可由Git历史追溯，无需新增重复备份。

## 批准的连续性公共证据
continuity角色将仅写 app .runtime/performance-baseline/media/continuity/summary.json 及该子目录素材检查证据；媒体角色可读取并合并，不读其通信目录。

## 2026-10-21 用户确认原生短窗口
用户明确选择“按阶段短窗口（推荐）”。A完整原生补录已正常保存并解析通过，直接复用。C/D整段真实剪辑与py-spy采样保持完整；C找球、D找球及CPU姿态阶段各录8秒原生窗口。只改docs/ai控制/解析工具，不改冻结应用/算法源码。窗口由现有GET状态stage真实进入后4秒触发，记录请求观测与实际trace起止；不能推算全程GPU利用率。普通应用UID501，管理员仅py-spy采样器，可能仍由系统逐次弹窗。原始计划9次完整流程，因A原生补录实际10次，正式六次未重复。全部有效证据及输出核对后仍须独立验收。

## 独立验收前的公共工具位置
为保持角色通信目录仅存输入/输出、让验收能独立检查实际工具而不读开发通信，三个现行脚本已迁至 controller/：native_profiles.py、python_profiles.py、validate_outputs.py。原位不保留兼容入口。目录深度未变，ROOT计算与运行语义不变；所有已完成运行的旧命令/路径属于历史记录，当前操作以controller新入口为准。当前人类报告/入口会同步更新，原始测量与失败证据不改写。

## 第二轮修正与复验
第一轮独立验收版本r1-20261021-final（402文件SHA f17a09efbd093a4a3a303960d2d407495c1667e08d990138f83413ab42484edc）未通过，唯一P2为SVG可见残余被误称精确self/完整识别分母。功能、103后端、5控制逻辑、10成片、三短ON/OFF、原生及其尾部限制均由验收独立核查通过。第一轮报告保留verifier/output.md。现仅修正公共Python摘要字段/解释、从原SVG重算的小摘要、人类报告与SHA索引；147产品实现和全部原始测量/输入/采样不变。修正后重新冻结交同一独立验收上下文复验，不重新鉴权、不重跑模型。

## 已通过第二轮独立复验
版本r2-20261021-svg-semantics，402文件SHA 394e22e11d6dc9874d6d28728741b7169765c6d1eae32f9dce9582d40a912597，功能/代码/文档均通过。唯一P2已修正，不改变原实测与147产品文件。已同步任务分支已完成、待人工确认状态，正做状态收尾核查。主线仍进行中，只有获确认后才集成。

## 最终状态
第二轮及状态收尾均通过独立验收。最终402文件树SHA a51b0b39a0900a7f6e47a8496ec2a88c0e1b71a8f7c3eb62733f6bc1ee094665，结果见verifier/output-r2.md与output-closure.md。任务分支已完成，待人工确认；保留本worktree与全部有效原始证据，授权仅本地提交已验收内容，不推送、不合入。develop保持进行中，原工作目录其他修改与outputs未触碰。正式每输入一次，原生阶段限制与C缺样均保留；未执行30分钟/准确率/打包/完整浏览器验收。

## 用户确认集成
用户已确认交付并授权合入 develop。集成后保留本报告、性能基线任务工作树和原始有效测量证据，供后续优化对照；未推送、未删除工作树或测量证据。
