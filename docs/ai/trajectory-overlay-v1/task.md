# 二维球路分析与剪辑叠图首版

## 最新用户指令（2026-10-23）

- 用户最新明确授权“合入develop”，替代此前等待人工查看且不提交/合入的限制。按已确认首版集成，保留15/16“演进中”及feature中的高远球精度/场景扩展方向，不再启动独立算法或视觉复核。保留develop其他未提交工作，不推送。集成后保存必要真实缓存与成片证据，再归档本任务worktree。
- 用户要求移除roadmap中“二维球路分析与剪辑叠图”的独立章节，范围与研究说明归feature专题；路线图保留15/16简要任务、状态、依赖及feature入口。本轮仅文档整理。
- 用户要求路线图15/16及相关图表统一标记“演进中”。最新纠正：高远球精度不足、仅支持A场景需扩展两项具体方向维护在球路专题optimization.md，roadmap只保留简要状态和入口。本轮只更新文档，保留尚未集成状态，不继续算法开发或独立复核。
- 最新补充已确认：“任务位置”指“人物位置”。非末拍起点不合规时，用击球时刻同一击球者的场上位置估计；缺少该时刻时用前后人物位置插值。终点可用下一次击球位置；估计后仍不符合两条限制则隐藏。仅修正不合规箭头，末拍坐标继续豁免。
- 已停止自动独立复核，用户人工查看；不得自行恢复复核、提交、合入或推送。上一轮产物保留。
- 新增非末拍箭头的两项限制：两端在当前单打场内（含边线），且分处球网两侧；每回合最后一次真实击球豁免，未知占位段不算末拍。
- 失效策略：先尝试从人物位置修正不合规起点，再按需用下一次真实击球位置替代终点；仍不合规则隐藏，不强行裁剪/捏造坐标；原未解析段保持未解析。
- 直接处理既有真实逐拍结果并重新导出，追球/人物模型、标定和物理拟合均不重跑。本次改动完成后交用户人工查看。
- 人物位置补充已实现：48项相关测试和差异检查通过；两次起点估算仍越过底线，成功恢复为合规箭头0次，新样片与上一版画面一致。当前产物为 `.runtime/trajectory-overlay-v1-product/results/player-origin-constraints/`，详见产品报告和该目录summary；保持人工查看、未提交/集成状态。

## 授权与目标

用户明确要求使用仓库 run-task-workflow skill 实施任务15和16，并于2026-10-22授权按照已确认计划实施。仅固定机位比赛高视角单打；同时交付独立二维球路模块及最终MP4内小球场同步箭头。初版基本效果，独立审核明显错误，不承诺量化落点精度；算法与产品并行，不以待定数值门槛阻断开发。

最新决策优先：先自动标定，不增加人工标定UI；高视角默认开启、上传页可关闭；固定右上角、完整当前拍箭头、下一拍替换、不留历史；预计落点不可合理预测时允许下一次击球位置或实际落地点代替；成片箭头统一样式，终点来源写结果和报告。测试视频自动标定必须跑通，失败作为缺陷修复；本轮不扩展产品化降级策略。场边/个人视角、公开发行包、推送和集成均不在本轮范围。

## 路径、分支与基线

- 主目录：/Users/bytedance/workspace/experiments/smash-suite（develop），已有未提交修改须保留；只在此更新本任务认领。
- 任务worktree：/Users/bytedance/.codex/worktrees/trajectory-overlay-v1/smash-suite
- 分支：codex/trajectory-overlay-v1
- 基线：94a8465（develop已提交版本）
- 主目录的路线图15/16尚未提交；任务分支只移入本任务说明，不移入其他脏改动。
- 本worktree依赖清单与基线一致；.venv、根/前端/文档node_modules、datasets local以忽略的符号链接复用主目录。源码、测试、输出均从本worktree运行。
- 已有权重：主目录/.runtime/product-data/models/{ball_track.pt,yolo11n.pt,pose_kpRCNN.pth}；不要重新下载或改客户端环境。

## 冻结的共用接口（轮次1）

分析模块 exports：

```python
from modules.trajectory import ObservationLog, analyze
with ObservationLog(point_path, source=source, info=info, weight=weights['ball_track.pt']) as sink:
    predictions, details = recognize(..., observation_sink=sink)
paths = analyze(source, info, predictions, point_path, weights, directory, progress)
```

- recognize新增可选observation_sink=None；高视角每个真实输出调用sink(frame, point)，frame是推理所用1920x1080的TimestampedFrame，point是对应ShuttlePoint。不能改变原回合判断、时间、阈值或关闭时行为。源首帧时间归零，毫秒。
- ObservationLog是context manager且可调用，逐行写frame_id/timestamp_ms/x/y/confidence（x/y为1920x1080参考像素）；同名 .meta.json保存源路径/视频SHA256、模型SHA256、参考尺寸与完成状态，供离线复算判断是否可复用。只缓存观测，不缓存图像，不把低分峰当真实球。
- analyze(source:Path, info:VideoInfo, predictions:list[dict], point_path:Path, weights:dict, directory:Path, progress:callable)->dict；内部消费冻结观测，可读视频作自动标定和人物检测，不能再次运行TrackNet。
- 输出schema_version=1；coordinate_system包含unit='m'、width_m=5.18、length_m=13.4、方向x左到右/y远到近；court包含image_from_court、reference_size=[1920,1080]及诊断（允许projection/controls）；shots含rally_id、shot_id、start_ms、end_ms、start_xy、end_xy、end_kind；diagnostics保存整体统计。start/end_xy为两个有限米坐标或None；end_kind=predicted_landing|next_hit|detected_landing|unresolved。允许添加必要诊断，不能删除/换名这些字段。
- 球场坐标原点是远端单打左底角(0,0)，近端y=13.4，双打边线x=-0.46/5.64，球网y=6.7，网柱位于双打边线。允许场外坐标，不将其裁到界内。
- product请求字段show_shot_paths:bool=True；只在camera_type='high'且开关true时启用，其他视角前端不提供并不触发分析。worker保存ball-observations.jsonl及meta，shot-paths.json；分析耗时计入既有recognition阶段，不新增耗时字段。
- 产品在app/trajectory_overlay.py把paths+export_ranges映射为ASS矢量文件。modules.media.video.render新增仅关键字overlay_ass:Path|None=None，在既有剪辑及setpts后烧录；媒体层不依赖羽毛球算法模块。FFmpeg实际已核对支持ass/overlay/subtitles，复用现有imageio-ffmpeg，不增依赖。

## 开发分工

- 算法开发：只写modules/trajectory/**、modules/rally/recognize.py、modules/rally/tracknet_rally.py、modules/rally/scenarios/high.py及对应rally测试；负责真实球点记录、自动场地标定、逐拍起终点、离线CLI、模块文档与报告。自己的通信目录developer/algorithm；不读产品或验收通信目录。
- 产品开发：只写apps/video-clipper/**、modules/media/video.py及对应media测试；负责前端开关、请求/state/worker集成、ASS叠图、导出和应用文档；自己的通信目录developer/product；不读算法或验收通信目录。
- 主控：需求/验收标准、路线图、根/文档入口、状态冻结、任务材料、联调和检查。不得把模拟输入称为真实功能验收。
- 需要变更冻结接口先反馈主控，不直接修改对方文件。

## 实测输入与缓存

现有历史outputs只有回合区间、统计和成片，真实球点缓存已缺失。首轮为两份真实视频各补采一次TrackNet输出，冻结后重用；不每轮重跑。视频为主目录datasets/badminton-v1/local/rally/下：

1. m1-short-a1-01-20261015/clip.mp4（SHA256 e2ea56c398507cc0c1679088121f26ac5a0d6b23ad12502151fb855b13966ef2）。
2. m1-a2-01-20261019-workerfix/clip.mp4（SHA256 0ae60f5564e9fed6058c87cdc573b5a07d5e4d8ef6137245b67f59ede5d0edc9）。

先完整FileFrameSource预检源文件。采集与实验放modules/trajectory/.runtime/，正式报告放modules/trajectory/reports/及apps/video-clipper/reports/；临时服务/任务数据必须使用本worktree/.runtime/，不得操作主目录已有服务。可以复用原有已确认回合区间启动离线实验，但最终须真实产品流程接通。

## 验收标准

1. 两份输入上自动球场标定、真实追球观测/人物检测、逐拍分析及最终MP4叠图全流程跑通；不得用手工点位、模拟球点替代真实结果。
2. 独立验收观看真实成片与代表性连续回合，检查场地线、起点对应选手、球路大致方向/区域、箭头每拍切换、漏拍与跳变，修复明显错误；报告预测/替代/无结果数量和失败案例。此为首版功能与合理性粗检，不能表述为落点准确率或独立数据集效果达标。
3. 图中有羽毛球单双打场地线，右上角、高约画面30%、深色半透明底/白线/统一颜色箭头；回合结束清除箭头，不能在补时或下一回合残留旧箭头。MP4内实际烧录，网页预览与保存同一成片。
4. 工程测试覆盖部分漏检、终点替代/未解析、回合切换、补时合并/裁界/拼接、非零首PTS和VFR；箭头切换误差不超过一源帧。关闭球路后原始回合结果与音画/时长/画质行为保持一致。
5. 运行pnpm run test:backend、pnpm run typecheck:frontend、pnpm run dev:frontend、pnpm run docs:build、git diff --check。有真实视频/模型验证，模拟单测不能替代。
6. 独立验收分别给功能/代码/文档结论；报告与冻结代码内容摘要匹配。任何后续实现变化重新验收。
7. 完成后在任务分支本地提交实现和报告，保留worktree，不push、不合入；任务分支15/16可标已完成待人工确认，主目录develop仍进行中并保留认领。用户确认实际交付后才另行集成。

## 当前状态与恢复

阶段：轮次1独立验收未通过，进入轮次2返工。117后端测试及全部构建通过，真实缓存复算可重现、产品烧录同步也通过；但A1 24.64–28.48秒、A2 73.92–76.12秒多拍合并成错误长箭头，且缓存读取未拒绝截断文件。先修复算法与缓存完整性，再复用缓存重新导出、冻结并独立复验；不得标记完成。应用README冻结状态也需同步。连续无进展轮次=0（首轮已产出实际功能与独立缺陷证据）。

最新阶段：轮次2已独立复验，123后端测试与文档构建通过，缓存和原目标窗口已改善；仍发现A2网前弱推断事件影响真实击球方归属并吞掉后续近端回球。主控与验收用完整画面/真实球点复核并纠正了最初将76.52秒恢复动作当触球的描述，功能仍不通过。进入轮次3修复该通用机制；前轮均有实际改善，连续无进展轮次仍为0。当前验收记录归档 `verifier/round2-*`，实际证据 `.runtime/trajectory-verification/round2/`。

2026-10-23已回应用户的缓存复用问题：当前两样本共6621帧日志齐备，后续标定、逐拍分析与叠图迭代直接复用；原先仅有回合区间的旧结果不足以替代球点。最终证据须区分真实观测离线复算/导出与此前开发版本的API联调，不能将后者称作冻结版本一次完整API重跑。

轮次1验收记录已归档到 `verifier/round1-*`，实际证据副本在 `.runtime/trajectory-verification/round1/`。轮次2算法修复已冻结，正在仅用保存的观测和当前逐拍结果重新导出；77项算法/回合检查通过，效果等待独立复验。

轮次3代码冻结摘要：`6f6379e21c04756264a5f7c6153c1581e66146a30c5efa457cb408c4fd3c9f71`；逐文件内容摘要见 `verifier/freeze.json`。实现保持停止，产品证据完成后启动独立复验。
恢复：先读本task与相应角色input/output，核对git状态、活动进程和当前轮次；不要另建worktree或重跑已有观测。

轮次3算法已冻结：两源全部7回合原帧检查收敛，81算法/回合与127后端检查通过；当前只复用缓存生成本轮实际成片，待独立复验，未标记完成。
