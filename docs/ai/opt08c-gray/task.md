# OPT-08C 灰度输入适配试验
用户授权所有确定项/高优先级尝试、细节取舍及验收后集成不再确认，不push。只TrackNet三帧RGB9→gray3，size288×512/float32/原权重/阈值/后处理不变；不做人检灰度、不训练、不下载、不改实际尺寸。三变体color9（原版）、gray9（cv2 BGR2GRAY后GRAY2RGB，保留9通道与原网络）、gray3（同cv2uint8 gray→float div/resize一通道，三帧cat3；每帧对应RGB权重求和，偏置和后续层完全相同）。fold在CPU原权重load后、eval.to(device)前，对conv2d_1.conv.weight [64,9,3,3] reshape(64,3,3,3,3).sum(dim=2)，in_channels=3、保留所有stride/padding/dilation/groups/bias；不要误sum时间轴或折BN。数学等价只针对gray9，不等价color9；真实浮点积累差需记录，不宣称严格位等价。
先实验runner不生产开关，优先复用已集成08A.run与07A完整识别统计，不复制大块runner；派生源的唯一替换断言、真实类绑定、权重/视频SHA/MPS/路径/runner+派生SHA可核对，failure显式。定向检查已知first-layer folding保bias/后续参数，真实派生预处理与灰度复制参照的值/通道对应，输入不变，3帧顺序正确。
数值probe三组实际A帧（源4秒/25秒/50秒附近的原生相邻3帧，记录真实fid/PTS/图像SHA；仅前缀读取取样，不冒称EOF）。检查gray9与gray3的实际[1,9,288,512]/[1,3,288,512] input、首层输出/完整热图max/mean差、torch.allclose默认判定及点值/候选差异，保留实数等价与浮点实测区别；保存后续层参数逐key不变的SHA，源图未改。原色作信息改变对照，不要求数值等价。只保存必要可重算指标和身份，不存整片图像或巨大热图。
主控串行运行probe后，gray3完整A-short当前真实EOF4200/1400窗，复用08A三尺寸试验原色288控制（原始/导出、4200点与时间，源码生产hash相同）作输出/成本参照。成本不同独立单次，不能稳定收益结论；若输出变而无匹配人工标签保守不采用，不补C，不降低效果口径。若有保留依据才补C，保留实际生产候选需后端测试和回归。所有步骤由独立验收重跑关键probe/真实candidate并分别功能/代码/文档结论后集成，保留原始证据并归档。

## 唯一路径与版本

- 实际目录 /Users/bytedance/.codex/worktrees/opt08c-gray/smash-suite，起点develop c62527982a6bcd6fc95cb00572f346d52d36fffb，准备分支codex/opt08c-gray。
- 输入沿用主目录apps/video-clipper/reports/performance-first-round/inputs.json固定A-short（媒体SHA e2ea56c398507cc0c1679088121f26ac5a0d6b23ad12502151fb855b13966ef2）；缓存权重主目录apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models，按ASSETS核对。
- 08A原色288控制raw/result/run/point观测已保存主目录apps/video-clipper/.runtime/opt08a-size/A-short-288x512，源predictor d8208470e973ff4388d8c34be54f19609a50a61571e72aaa3ed45dcaf8c34152，与本任务生产代码相同；作为当前单次观察参照，不称本轮新原色重跑。
- 主目录已有规划/ideas/图片/outputs用户改稿不纳入；不改原08A/07A脚本，不下载依赖或模型。临时.venv只读复用主目录，先比对pyproject。

## 流程与当前阶段

第1轮开发及真实执行已完成：probe三组九帧，gray3 A-short完整EOF4200帧/1400调用。原色控制为已集成08A镜像；raw/export差异为控制未覆盖840ms、新增240ms。本轮灰度候选不采用，不补C、不改产品。正式报告和局部viewer证据已收口，开发暂停，当前冻结后独立重跑关键probe与完整候选；功能、代码和文档分别验收。用户已授权验收后本地集成，不push。

## 集成准备

第1轮独立验收通过，任务本地提交 `c36b0dc673d9cde65f160fbf6e8e2cd629174b68`。按用户授权保存到主目录准备集成；原始/独立运行镜像与SHA见 evidence-preservation.json。没有产品修改，本轮不采用gray3。测量基线和冻结记录为历史验收来源，不随主线元数据更新。
