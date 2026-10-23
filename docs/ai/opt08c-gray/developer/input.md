# OPT08C 第1轮开发：灰度输入与首层折叠实验

仅本worktree，先读task/根README/TrackNet与rally对应README。禁止读取任意verifier通信目录；只写自己的output、docs/ai/opt08c-gray脚本/检查及本任务正式报告。不要改生产、08A/07A入口、依赖、规划。先核对HEAD c62527982a6bcd6fc95cb00572f346d52d36fffb及status，创建分支codex/opt08c-gray；比对pyproject后链接主.venv，不安装。此轮不运行模型/视频，主控串行执行。

## 入口与复用

实现run.py --variant color9|gray9|gray3 --case A-short --inputs --models --output。复用已集成docs/ai/opt08a-size/run.py、docs/ai/opt07a/recognition.py，不复制大块main。可importlib加载08A helper，将其derive_source覆盖为本任务候选派生（内部先调用原derive_source做288映射/point记录），再以--size288x512调用其main；完成后run.json补记实际gray_variant/channels、本任务runner/源/派生SHA。底层helper内部variant标签必须说明是复用层，而非误称尺寸试验；实际class、派生源码保存且SHA可核对。动态绑定发生在recognize导入之前。所有变体输入图像不变，不留整片图像，4200points记录复用；prepare/write/recognition计时边界如实。

color9为不变RGB9；gray9在原cv2 BGR2RGB处改cv2 BGR2GRAY后GRAY2RGB（uint8再float div_/resize288512）；gray3同uint8灰度后tensor.unsqueeze(0).float().div_(255)，一帧1通道，三帧cat3。每处文本替换assert一次，保留antialiasTrue、帧顺序、缓存/下游逻辑。gray3只在load_state_dict后eval.to(device)前折首层：conv2d_1.conv.weight [64,9,3,3] CPU reshape(64,3,3,3,3).sum(dim=2)，Parameter替换weight、in_channels设3，bias及stride/padding/dilation/groups和所有其它state保持；不换BN或再训练。可将一个小_fold_first_layer(model)函数定义附入派生源码，在原init调用它，测试直接调用同一派生函数（避免测试镜像算法）。未知结构直接assert，不加宽泛兼容。

## 数值probe

实现probe.py --inputs --models --output，MPS固定、torch4、保留cv.setNumThreads(1)并记录实际18；三组真实A相邻帧：从源时间4000/25000/50000ms后首个frame_id%3==0开始连续三帧，记录实际ID/PTS/图像SHA。FileFrameSource按真实PTS遍历至第三组拿完即结束，仅前缀取样，明确不称EOF，不保留整片。捕获取样逻辑与三帧邻接要有定向检查。

同每组比较三变体，forward pre/post hook记录实际model输入shape、首层线性conv输出与完整heatmap；仅保留可重算数值指标/各张量SHA/点与candidate差异，不保存大数组。模型输入gray9各时间帧的RGB复制值应与gray3对应灰度严格一致；保留bias/其它state逐key一致，首层weight求和可复算。gray9与gray3首层/heatmap记录max/mean absdiff、torch.allclose默认判定及精确相等数/总元素；点/候选差异如实。color9与gray是信息变化对照，不要求等价。此处不测速度、不把浮点接近称位级或原彩色等价；不要以人造零点/假图代替。

## 定向检查和交付

使用合成小图/stub或CPU未训练TrackNet层，不加载真实权重或媒体：检查同一实际fold helper的通道分组/偏置和后续参数不变；真实派生预处理gray9复制vsgray3值/时间帧顺序/原图不变（可stub后续model）；目标前缀采样/相邻性。不写字符串镜像型无效测试或大兼容封装。

输出自己的output：第1轮/版本/文件SHA、入口方式、实际检查与未跑模型事实。不要虚构正式结果，不暂存提交。完成入口和必要定向测试/diff检查后暂停，等主控运行。数值probe和真实候选完成后再由主控决定报告/取舍。

## 真实执行前主控最小修订

probe.py未在导入modules前sys.path.insert(0,str(ROOT))，共享venv的editable安装可能先载入主目录代码；必须与run/08A一致先插入worktree ROOT，并核对FileFrameSource、生产predictor及TrackNet、assets实际__file__在本ROOT下，把真实路径和SHA写probe。失败直接报错，不静默跨checkout。

FOLD_HELPER当前detach后的weight.requires_grad必为False，改为保留原conv.weight.requires_grad值（在detach前取，Parameter用原值），不无意改变参数属性。模型只推理，但不要引入与通道折叠无关的属性变化；补已有fold测试核对属性。

run.py外层TemporaryDirectory写temp_source从未传给helper（内部08A main自行派生/保存），删这份无用临时文件/上下文及tempfile import，保持patched helper派生/元数据/失败处理；不要改08A/07A。两个load helper目前重复8行，可最小合成一个带模块名参数的helper供两次独立实例加载，避免复制；不做其它重构。

未跑任何真实模型，此时修复后重跑4项定向检查与diff/py_compile，更新output的SHA后暂停；主控随后串行实际probe。不必先冻结，没有独立验收启动。

## 第1轮实际结果与报告收口

主控已串行实际执行probe和完整gray3：runtime/opt08c-gray/probe/probe.json、A-short-gray3/{run,result,statistics,resources,derived_predictor.py}均存在。探针三组9帧：gray9/gray3复制输入严格同值，除首层weight/in_channels外state一致；首层maxabs5.7220459e-6，heatmap三组max约5.96e-7/3.76e-7/2.20537e-6，默认torch.allclose均False。九点x/y都相同、5个confidence不同；candidate有6帧列表不同。不能称位级/默认allclose通过，也不等价原彩色。

完整gray3 25.009133416s、EOF4200/1400组，与先前08A原色288控制29.966605208s不同单次观察（非本轮新原色重跑）。原始区间发生840ms缺失/240ms新增（请从实际JSON独立重算逐段，导出500ms缓冲单独算）；无匹配人工标签，不把缺口当已证明真实漏球，但无法证明既有效果保持。本轮gray3不采用、不补C、不改产品；也不做新训练，记录当前灰度适配尝试结束，不否定所有灰度方案。

请先完成汇总script及正式apps/video-clipper/reports/opt08c-gray/{README.md,summary.json,probe.json}：复用08A汇总纯interval/point/resource函数即可，避免复制240行汇总；比较source code哈希，明确原色控制的主目录镜像及hash（源08Aworktree已归档），保存原始raw/export、逐段差、点差、实际模型工作量、墙钟及准备/嵌套范围、采样资源。probe JSON原样复制核SHA，不覆盖原始任何run数据。README先结论、数值含义、区间/成本、证据与限制，简洁分节。主控随后补统一viewer/局部视觉记录（暂不编造截图或人工结论）；初版报告可以先留查看器由主控补记，不阻塞汇总。

更新output事实/文件SHA，task当前状态主控另改。原始成本/效果记录不重跑；必要5项检查与diff/py_compile后暂停，不暂存提交。不需要改既有runner以免改变已测代码版本；保留当前实际运行入口。

### 统一查看器补记（冻结前纳入报告）

主控已保存modules/models/tracknet/.runtime/opt08c-gray-review.json，使用固定review.py启动http://127.0.0.1:60032/，同一A片两行：原彩色/折叠灰度，无truth。实播源3.000→11.020秒，时间轴同步；随后点击时间轴定位3.715秒，界面显示原彩色保留、灰度删除。主目录apps/video-clipper/.runtime/opt08c-gray/viewer.png为这一3.715秒时点的原始截图（当前最终版本）。这只是算法边界差异的局部定位，没有人工审核起止或全片标注；不根据单张画面宣称真实漏球。

请将本任务viewer JSON原样复制正式reports/opt08c-gray/review.json，主目录当前截图原样复制正式viewer.png，核对SHA/大小；README/summary补准确的播放范围/单张时点及对应链接，不编造额外视觉结论。无需更新已保存probe/run，不重跑任何模型。完成报告/输出后暂停。

## 报告冻结前最小修订（同第1轮）

仅报告收口，不重跑模型。summarize.py limitations 仍写 viewer pending，与已完成播放/截图矛盾；改为实际源3.000–11.020秒播放、3.715秒局部定位且没有人工标注/全片复核。code_comparison 中把继承08A helper 的 runner_sha256 语义写清，补实际 candidate_run["opt08c_runner_sha256"] 字段。README 首句缩到本轮 gray3 不进入产品，不泛指否定后续所有灰度方案；summary/probe 数据入口改为相对 Markdown 链接。重生成 summary，核对副本SHA、语法及diff check，更新自己的 output/SHA，然后暂停。禁止改生产、原始runtime与验收输入。
