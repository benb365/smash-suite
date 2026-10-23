# OPT08A 第1轮独立验收（冻结后启动）

唯一目录 /Users/bytedance/.codex/worktrees/opt08a-size/smash-suite；codex/opt08a-size；基线4910e1e5af66d4baebc8373bc6d138645510a996（07A已集成）。用户授权自动取舍及验收后集成，无需再确认。读取task、本input、acceptance-freeze.json、指定代码与真实证据；禁止读取任何developer通信目录。只写自己的output.md、.runtime独立结果；不改实现/报告/门槛。开发已暂停，开始/结束核对freeze SHA与HEAD。

## 功能

三档A完整真实运行在apps/video-clipper/.runtime/opt08a-size/A-short-{288x512,216x384,144x256}，检查run/result/statistics/resources/derived_predictor.py及正式summary。媒体/ASSETS缓存权重SHA、MPS、torch4、cv实际18、真实模块路径、派生源码与runnerSHA均须一致；每档1400组三帧/4200真实EOF，不能只信summary布尔。

实验只改实际TrackNet输入尺寸和热图坐标比例；288控制的raw/export应与07A summary candidate完全一致，新控制时间29.966605s，216为22.037524s，144为19.712088s。检查动态类在recognize导入前实际绑定、源/派生SHA可恢复，真实模型输入不是只缩小前图再放回原尺寸；坐标映射用实际heatmap shape。三池化结构尺寸皆8整除。其余归一化、RGB、抗锯齿、三帧、阈值及规则保持。

关键独立重跑：run.py --size 216x384 --case A-short --inputs /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/reports/performance-first-round/inputs.json --models /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models --output apps/video-clipper/.runtime/opt08a-size/independent-216x384。新目录，完整EOF、真实MPS；与保存216的4200points和raw/export严格一致，时间可波动。只此完整关键重跑，不跑C/D/导出/长片或全组。

另做三档实际首组三原帧的尺寸smoke：用FileFrameSource读取A前三张真实图并normalized，分别加载保存的三份derived_predictor.py（相对包名modules.models.tracknet下独立模块），模型MPS首层forward prehook记录实际input tensor shape，检查分别[1,9,288,512]、[1,9,216,384]、[1,9,144,256]，输出heatmap形状与解码比例。可用model forward hook记录output shape，不改输入/输出数值。smoke是前三帧检查，不冒称完整EOF；完整EOF证据来自上项。不修改正式runner或derived源码；临时probe放.runtime并保留检查结果。主控不并跑模型，串行执行。

从原始result独立算raw/export并集差与逐段缺口/新增：216各缺80/新增6760ms；144各缺880/新增2040ms。不得把按顺序zip配对当人工回合匹配，当前各5段可作顺序诊断。点值比较4200逐帧按调用/点位置对齐，均三帧组全EOF时成立；核对两缩小尺寸字段变化数/坐标差，不把数值差当追球准确率。核查资源采样约1秒、父/子计时嵌套、准备/写盘范围如实披露。

## 取舍和标准

本轮两候选不采用，不补C、不改产品。输出变化且无匹配人工标签，不能证明既有效果保持，按保守门槛不保留；不是已证明真实回合损失或准确率不达标。也不能因为单次快就忽略80ms缺口/额外保留，更不能宣称整个降尺寸方向无效。用户不再逐项确认不等于放宽效果门槛。

## 代码/文档

执行3项test_run.py（stub/合成检查）及diff检查全部新增文本；确认没有产品/依赖/07A脚本差异，内存只保存点元数据。summarize只读取保存JSON、可确定性重算；无需产品后端/前端全量测试。检查报告先结论后表格/限制，当前新288控制与历史相同输出的来源区分，截图仅13.022s时点，实际播放器8→17s不是逐帧人工审核。view JSON仅三算法行、没有truth/绿色伪人工标注；首PTS91ms与片长168s确实来自源。截图与主目录原图字节相同。

## 输出

output写第1轮/冻结一致性，功能、代码、文档分别通过/必要修订；实际执行数、独立真实重跑及尺寸smoke、精确边界/未执行项。写完暂停，不暂存提交。需要修订时只提出最小问题，不自行修。
