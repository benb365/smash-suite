# OPT09A 第1轮独立验收（冻结后启动）

唯一工作树/task列明的codex/opt09a-single，读取task、本input、acceptance-freeze、实现和指定证据；不读任何developer通信目录。只写自己的output与.runtime独立结果，不改实现/报告/标准，不暂存/提交。开始/结束核对freeze SHA/HEAD，开发暂停，主控没有并行模型；本机真实MPS命令设置require_escalated，受限进程MPS不可见不等于硬件不可用。

按task完成功能、代码、文档分别结论，保守不采用试验不等于准确率失败。关键独立重跑一个完整C-short候选（主控冻结果后指定native或shifted）与实验定向边界检查；另一候选核对完整EOF证据、实际窗口和所选流覆盖/真实来源、人物调用/selected_people、raw/export并集差异可独立重算。旧dual控制仅主目录opt07a/candidate/C-short镜像，同视频/权重和生产SHA对应，不称新dual跑或稳定性能收益；无匹配truth不加人工行。

实际完整C5400帧；native预计1800次/5400输入/5400miss0hit；shifted1801/5403/5400miss3hit；人物均900图225调用。原observe内部计数与最终selected返回流分开，不将短内部native视为最终观测丢帧。三帧顺序、frame0/真实EOF末组、所选5400原ID/PTS、selected两参数同流及observed_candidates去重/phase来源语义须核对。原阈值/人物/下游/production都不改。对任意9/10/11帧尾数测试必须真实覆盖尾帧，N1/2不假造三帧。

只执行必需项，不扩展新输入/模型/长片或整套后端前端；如代码实际采用生产再追加对应产品验收。已有固定viewer由主控实播/对齐记录可核对，独立浏览器不可用可明列视觉复看未执行，不能冒称看过。报告一页为宜，真实复跑/检查数、三个结论、必要最小修订/限制写清即收口暂停，不无限扩展审查。

## 本轮冻结范围补充

关键独立重跑指定 shifted：.venv/bin/python -u docs/ai/opt09a-single/run.py --variant shifted --inputs /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/reports/performance-first-round/inputs.json --models /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models --output apps/video-clipper/.runtime/opt09a-single/independent-C-short-shifted。require_escalated才能访问实际MPS。与冻结shifted的selected_observations/IDs/PTS、model_windows（points/候选数量）、peoplefeatures SHA及raw/export逐值相同；墙钟允许波动。不要重复跑native或dual。

主控两次真实结果：native raw并集缺5300ms/增10768，export缺5300/增11768；shifted raw缺3167/增2900，export缺4167/增2900，原首段7700–10800在shifted消失。native/shifted所选各5400且同PTS、peoplefeatures SHA同、选人同dual；二者当前都不采用，不改生产，不否定所有单组设计。原9/10/11与1/2帧检查为6项，fake peak记录window start/slot以验证真实来源和EOF不覆盖既有上下文。无新增phase字段到原始observations；下游observed_candidates的phase为合并来源标签0。

主控固定viewer已实际播放6.018→12.020秒、三轴同步，随后8.135秒截图显示dual/native保留、shifted删除；正式报告含原图副本/SHA。只局部定位，不是人工起止/全片标注。报告来源路径已由tmp投影修正为实际worktree，不应残留/tmp/opt09a-artifacts。主控D基准运行已结束，验收独立MPS期间无其它模型/测试。建议用JSON解析与目标字段比较，勿把整个几MB observations倾倒到输出；功能/代码/文档分别结论，一页收口。
