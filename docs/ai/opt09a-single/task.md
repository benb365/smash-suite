# OPT09A C 单组找球试验

## 授权与范围

用户授权按顺序完成全部确定项/高优先级试验，后续细节、候选取舍及独立验收后本地集成无需再问，不push。当前试验只比较C-short当前双组、仅native与仅shifted；不改人物/轨迹/判定阈值、不训练、不下载、不改生产。当前短片没有SHA匹配人工标签，输出改变而无效果保持依据时保守不采用，不冒称真实漏失/准确率。

固定输入主目录 apps/video-clipper/reports/performance-first-round/inputs.json 的C-short，SHA f270602edffd9c6b081cb0463de9aa97f6d1ef3027b0b16d86ab46941bb07f5c，5400帧完整EOF。权重仅缓存 .runtime/performance-first-round/combined-d/D-short/home/models，按ASSETS大小/SHA校验。MPS/torch4/cv实际线程记录；不并行测模型。288×512 RGB9 float32不变。

## 最小实验实现

复用 docs/ai/opt07a/recognition.py 的实际识别/预检/资源采样/统计，不改原helper。实验run.py用当前 recognize.observe 的 inspect源码，唯一替换断言派生函数并绑定 recognize.observe，不复制维护完整算法；保存派生源码、原/派生/runner SHA、实际绑定类/源码路径，失败显式。native条件只phase0；shifted条件phase1或首组queue[0].frame_id==0，原EOF恢复仍对真实最后相邻三帧推理。返回下游两参数为同一所选实际流，不补零/None/虚构观测。

注意native模式任意长度EOF：完整native字典加shifted中仅为缺失尾帧产生的真实观测，不能因N%3为1/2丢掉末尾；shifted模式选shifted完整字典。N<3不伪造观测；下游原短片报错保留。三帧组按原fid顺序，首尾边界来源日志可重算。下游 observed_candidates 静态统计第一流一次、重复候选会去重，phase变为合并来源标签0，不等于第二次推理；不要改phase消费或算法。

实际5400帧预计：dual3599次/10797模型输入/5400cache miss5397hit；native1800/5400/5400miss0hit；shifted1801/5403/5400miss3hit（1799shifted+首帧base+EOF末base）。人物仍900张/225调用，真实selected_people相同。原observe内部native/shifted count与最终selected返回流的语义分别记录，不把shifted模式内部native3当作所选流只有3帧。

轻量Predictor子类直接调用生产父类并记录实际frame_ids、points、候选数量；可以绑定recognize.TrackNetPredictor而不是派生predictor源，记录actual class避免helper旧variant标签误导。observe包装在返回时保存所选真实观测流（含原fid/PTS/candidates）、最终两流id/PTS完全一致检查、people features SHA（规范JSON）和真实window列表。保存raw/export/decisions/work量与采样资源。不保存整片图像或张量。未采用时只保留必要实验/报告，不留产品开关。

## 对照与判定

当前双组控制明确复用主目录 .runtime/opt07a/recognition/candidate/C-short，生产recognize SHA17fb4cfb4387a8394836bc9793e526c42cf139ec291d6ee890a9d09e7052adad，predictor SHAd8208470e973ff4388d8c34be54f19609a50a61571e72aaa3ed45dcaf8c34152，与本任务当前生产相同。旧worktree已归档，必须使用主目录镜像，不沿旧source_paths猜fallback。对应preservation清单核对。控制完整EOF5400/3599调用，97.745275167s为不同轮次单次观察，不称本轮新dual跑或稳定收益。保存其raw/export/诊断/decisions作参考。

两候选都完整C-short跑一次。逐段并集缺失/新增、选人、飞行与轨迹诊断比较；有输出变化且无人工证据就不采用，不追加其它输入或长片。若均未保留则无需产品后端测试，只最小实验检查；若实际保留需生产最小改动另行验收/后端测试。

## 检查与交付

定向检查用假帧/可记录predictor与detector验证真实派生observe：9/10/11帧三种尾数、native/shifted实际窗口与原frameID/时间全覆盖、首尾真实来源及无额外重复模型调用、人物每6帧调度不变；N1/2不构造三帧。唯一替换点断言与源码绑定检查。区间纯比较复用08A既有函数，不写镜像实现测试。

开发只准备run与有意义检查并暂停，主控审源码后串行真实运行，再开发汇总所属 apps/video-clipper/reports/opt09a-single/ 报告及viewer JSON；查看器只能仓库固定skill，缺truth无绿色行。局部画面只定位，不代替人工标注。开发暂停、主控冻结，独立验收重跑至少一个完整候选并独立核对另一完整证据、边界检查/报告；功能/代码/文档分别结论。完成本地任务提交后按授权集成，保全原始SHA证据与viewer sidecar再归档，不push。

## 路径、版本与当前阶段

唯一工作树 /Users/bytedance/.codex/worktrees/opt09a-single/smash-suite，分支codex/opt09a-single，起点develop c62527982a6bcd6fc95cb00572f346d52d36fffb。该起点含07A生产优化；08C仅实验报告，独立验收收口时先准备本任务，不并跑模型。主目录用户规划/ideas/输出改稿不纳入。pyproject已核对相同，临时只读复用主目录.venv，不安装依赖。当前第1轮开发仅准备实验入口和定向检查，随后暂停交主控审查及串行真实运行。

## 第1轮真实执行与冻结

主控串行完成native/shifted完整C-short，分别1800/1801次，最终selected各5400真实帧，people特征SHA相同且选人同旧dual。两者原始/导出区间均改变，本轮不采用，不改生产。固定viewer实播6.018–12.020秒、8.135秒局部定位，三轴同步；仅定位差异，无人工标注或全片复核。开发及正式报告已收口并暂停，当前冻结后独立验收指定shifted完整复跑及6项边界检查。

## 集成准备

第1轮独立验收通过，任务本地提交 `48ffa7e4fc463926e7f11b4930ba83065aed3837`。按用户授权保存到主目录准备集成；原始/独立运行镜像与SHA见 evidence-preservation.json。没有产品修改，本轮不采用两种C单组候选。测量基线和冻结记录为历史验收来源，不随主线元数据更新。
