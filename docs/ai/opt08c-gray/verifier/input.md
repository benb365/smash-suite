# OPT08C 第1轮独立验收（主控冻结后启动）

唯一目录 /Users/bytedance/.codex/worktrees/opt08c-gray/smash-suite，codex/opt08c-gray；基线c62527982a6bcd6fc95cb00572f346d52d36fffb。读取task/input/acceptance-freeze及实现/指定证据，不读任何developer通信目录。只写自己的output及.runtime临时独立结果；不改实现/报告/标准，不暂存提交。开发暂停，开始/结束验证freeze SHA和HEAD。用户授权细节及集成无需逐项确认，效果门槛不变。

## 功能与关键重跑

真实probe在apps/video-clipper/.runtime/opt08c-gray/probe/probe.json；完整gray3识别在同runtime/A-short-gray3。输入/权重显式为主目录performance-first-round/inputs.json及.runtime/performance-first-round/combined-d/D-short/home/models，按ASSETS及媒体SHA校验；MPS、torch4、cv实际18、288×512、float32。代码实际路径均在worktree，source/derived/helper SHA可恢复，派生类确实在recognize导入前绑定，不能仅信输出标签。

probe独立串行重跑一次（同probe.py与显式--inputs/--models，--output apps/video-clipper/.runtime/opt08c-gray/independent-probe）；三组实际源ID应102–104、627–629、1251–1253，原PTS与imageSHA一致。前缀取样在第三组完成后停止，不声称EOF；prefetch的额外decode帧数可不同。核对gray9实际输入[1,9,288,512]与gray3[1,3,288,512]按时间帧/RGB复制严格同值，源图未改。fold CPU发生在load_state后、eval.to前，仅将conv2d_1.conv.weight [64,9,3,3]按[64,time3,RGB3,3,3] sumRGB，in_channels3，bias/所有其它state/requires_grad/卷积参数不变。

核对gray9与gray3首层线性卷积/完整heatmaps的实际数值差、torch.allclose默认False及精确相等元素数；首次probe首层max5.7220458984375e-6、heatmap三组max5.960464e-7/3.762543e-7/2.2053718567e-6。这不是位级等价，不能因差很小写默认allclose通过。九个点gray9/3的x/y都相同，5个confidence数值变化，候选6帧列表变化；原color9相对灰度是输入信息改变，不能叫原彩色等价。逐项核对三变体state-key哈希及第一层权重可直接由原ASSET重新折叠验证，不信报告布尔。

完整gray3关键独立重跑一次：run.py --variant gray3 --case A-short --inputs/--models同上 --output apps/video-clipper/.runtime/opt08c-gray/independent-A-short-gray3。完整4200真实EOF/1400组/4200点，实际class及input_channels3，比较保存候选的raw/export/points严格相同；时间可波动。主控不并跑模型。无需color9或gray9完整跑、C/D/长片/导出。

原色控制复用主目录apps/video-clipper/.runtime/opt08a-size/A-short-288x512（已集成08A）：底层生产predictor/rally/profile代码SHA与当前相同；原saved source_paths的08A worktree已归档，使用这个明确镜像路径，逐文件SHA记录在主目录docs/ai/opt08a-size/evidence-preservation.json。其控制raw/export与已集成07A候选一致，识别29.9666052079s是先前单次观察，不冒称本轮新color9重跑。核查正式summary的raw/export并集缺口、新增/逐段位置/4200点数值差/工作量与资源实际可独立重算。

## 代码与文档

5项test_experiment.py（含True/False requires_grad参数化）、diff check及新增文本空白检查。没有产品、依赖、08A/07A脚本变化；不跑backend/frontend全量。probe无巨大tensor文件，只有数值/身份摘要和9帧采样，prefix source关闭；完整run复用既有统计和采样，失败显式，代码/派生来源可追溯。嵌套计时不加总，CPU/RSS/MPS是采样观测，不当精确峰值/稳定收益。

正式报告应先结论后必要数值、区间变化、成本、证据链接/限制：数学灰度复制等价、浮点实际差、原色信息变化三件事分别说清。当前人工标签SHA不匹配，不能将算法原区间当真值，也不能声称真实漏球/准确率不合格；发生输出变化未能证明保留效果时，按主控取舍保守不采用，不因速度放宽门槛。任何查看图仅仓库固定viewer，缺truth不加绿色行；复看不代替人工标注。probe不是EOF/测速，完整run才是EOF识别。

## 输出

第1轮/freeze摘要，功能、代码、文档分开结论；实际重跑、检查数、明确未执行/限制、必要最小修订。只写自己的output/.runtime，不自行修实现，完成暂停。
