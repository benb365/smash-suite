# OPT20 删除D未用于判定的全画面光流

用户已授权全部确定项目、不再逐项确认，独立验收后自动本地集成、不push。只删除D首遍全画面Farneback及仅为其服务的灰度resize/previous状态/运动量提取与中间传递；保留主场选人、appearance、完整逐人Pose、肩腕PyrLK及+1/+3/+5原时间调度、arm/high/feet和所有规则阈值。不并入其它D结构重构/单遍读取/降采样，不解除OPT02阻塞。

最小改动：recognize.observe删body_features import、previous_gray/time与nonlocal、personal gray/dt/Farneback计算，只留appearance=descriptors；players_v2.follow删body_motion透传字段，不改cost/匹配逻辑；trials.series删upper/art数组、body_motion取值、两者median与返回键，保留speed/present/ball等现有其它能力；body_features.py为唯一当前caller失效后删除。common/trials的RallyInterval仍被其它模块导入，不顺手清理。现有任何活跃使用先rg核对，不参考backup旧代码为当前契约，不保留虚假body_motion=None兼容字段。

只读路径证据：recognize.observe→people_flush Farneback→body_motion列表→players_v2.follow选择dict→trials.series upper/articulation；最终pose_context.extract只取series.ball，最终signals不含两运动量，select也不读body_motion。实际比较必须证明选人/raw/export/person-signals所有最终数组保持；不能仅凭静态死数据推断全片通过。

主控已在develop5bb39fa69181e86c21bde20e74d951f1cb2ca415启动当前D-short真实产品API对照（未改生产、无FPS上限），缓存权重/媒体均按现有benchmark核对，不下载。主目录 apps/video-clipper/.runtime/opt20-flow/baseline-report.json 与 baseline/D-short/evidence 保存当前结果/实际阶段/统计/pose signals/导出；这是本轮新完整D短片对照，不用历史ba0fd88计时冒充。benchmark运行时主目录仅用户规划改稿与本任务报告，不涉及生产改动。候选使用同input/models、同benchmark参数新独立目录；模型/CPU测量串行。

输入固定primary performance-first-round/inputs.json D-short，SHA360e3de1018a9656770ea432c903afba44cff29c0052f03ea65606a5200867fd，7527帧约250.9秒，pose两遍仍正常运行；此为短片，不重跑长片或全组。权重primary .runtime/performance-first-round/combined-d/D-short/home/models按ASSETS全部核对。MPS/CPU逐人pose/线程保持原配置，统计开关相同。实际product benchmark同时成片可完整核对MP4结构与原音轨，不为此复制新runner；baseline/current版本与SHA分别记录，单次不作稳定收益。

必要检查：pnpm run test:backend（PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false，require_escalated以允许已有进程检查）、每次diff check。删除纯死数据不写镜像实现的测试；仅现有检查缺实际规则保证时补有意义非依赖body_motion的follow/pose_context小fixture检查，切勿把Farneback零值fake当功能验收。真实D选人track IDs、raw/export、所有person-signals数组equal_nan比较逐值相同，决策trace/模型调用与姿态工作量保持；实际Farneback不再调用可由源码及窗口spy的必要小测试证明，保留PyrLK调用证据。完整识别/准备/成片分别计时，CPU/RSS/MPS采样不当绝对峰值。

报告归 apps/video-clipper/reports/opt20-flow；task/输入/流水docs/ai/opt20-flow。开发先最小修改及相关检查暂停，真实运行由主控安排。冻结后独立验收重跑关键真实D候选及必要检查，分别功能/代码/文档。通过本地提交，按授权集成，affected checks通过、SHA证据保全后归档，不push。当前无匹配人工标签不算准确率，但若所有下游结果严格相同可验本项等价简化；不把新历史观察当长期硬件/速度承诺。

## 路径、版本与当前阶段

唯一工作树 /Users/bytedance/.codex/worktrees/opt20-flow/smash-suite，branch codex/opt20-flow，起点develop 5bb39fa69181e86c21bde20e74d951f1cb2ca415。生产当前与D本轮baseline相同；09A只报告/独立验收，09B在其它工作树静态准备且效果数据缺口未解除，均未进入本分支。先准备本任务最小静态修改，不并行测试/模型。pyproject相同，临时只读复用主.venv。主目录既有规划/ideas/outputs草稿不纳入。

D当前baseline产品已完成：总322.016755875秒（准备0.578538375、识别308.514397875、成片12.923819625）；2遍15054解码、2432pose calls、5018pose converted、selected tracks[58,40]、13输出。仅单次当前对照，不是稳定性能承诺。

## 第1轮冻结验收

候选真实D完整API运行已完成，raw/export/decisions/13项signals及成片音视频完整解码均等价；后端107项通过。开发收口并暂停，冻结见acceptance-freeze.json。独立验收先静态核对，收到主控测量释放后依次107检查、D完整真实候选重跑及既有validate.py；不得与09B模型并跑。

## 主线集成

第1轮独立功能/代码/文档验收通过，任务本地提交 `f4772273b112ef358ac5345a18aabae37974ee0a`。按用户已授权自动集成到develop，不push。原始与独立运行证据已保全；107项后端检查将在主线集成版本复验。09B按用户决定保留待验收分支，无真实高帧率素材，不随本次集成。
