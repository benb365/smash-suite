# 第1轮开发输入

唯一工作树为task所列路径与分支，只读 task.md、本input、项目必需源码/README与指定输入证据；不读任何verifier通信目录。只在本工作树修改 docs/ai/opt09a-single 的实验run.py/test_experiment.py及自己的output；不能改task、标准、生产或旧helper。按task最小派生observe方案准备native/shifted入口和有意义的合成边界检查，先不做正式报告、不运行任何媒体/模型/权重；实际运行由主控串行安排。读真实源码确认替换唯一点与返回流，不依赖隐式重复调用判断EOF。输入/模型主目录路径必须显式，当前worktree所有实际模块路径均核对。避免冗余封装、兼容猜测。完成跑定向检查、语法及diff check，自己的output写实际实现、SHA、检查/未执行项与可运行命令，然后暂停。环境需本机MPS真实访问时使用require_escalated，不能因受限进程看不到MPS误判硬件不可用；本轮不启动真实模型。

## 真实执行前最小修订（仍第1轮）

主控已审源码，目前未跑媒体/模型。当前run.py重复了07A完整main的大部分哈希/初始化/预检/采样/执行/失败写出代码；task要求复用既有runner，不能只复用几个helper函数后复制整个runner。请将其改为调用helper.main（variant=candidate，case=C-short，reference-source为当前生产predictor，仅作hash），调用前绑定recognize.TrackNetPredictor与recording_observe；helper随后import同模块会用实际绑定。保留参数透传/sys.argv恢复，完成或失败后按run文件存在追加本实验metadata/observations/derived_source，helper失败仍重抛。不自行创建output目录挡住helper的新目录校验。删重复main逻辑与无用imports；真实完整统计/采样/ASSET验证由helper直接承担。

observe派生只须唯一替换正常phase条件与最终return，不改target或首窗seed，不新增第二段EOF循环/全局variant变量。原target=native ifphase0 else shifted、shifted首帧seed和原EOF真实tail恢复全部保留：native-only时原EOF会用实际native补齐shifted，并对N%3不足尾帧用真实末队列推理；返回所选native时 chosen={**shifted, **native}，保留native优先且只从shifted补缺尾帧。shifted-only时仅首native窗口+正常phase1+原EOF尾窗口，选择shifted。按chosen排序得到rows，直接return rows,rows,features。不要给原始观测行新加phase=0字段；observed_candidates自己给去重后候选的合并来源标记phase0，报告说明即可。记录wrapper可加覆盖/同fidPTS检查，不把这些诊断塞入生产派生逻辑。

RecordingPredictor.calls删未使用的完整candidates字段，只存ids/points/候选数；所选真实候选已在selected_observations保存。ROOT无条件插到sys.path首位。保留实际类绑定/所有模块路径检查；记录helper与实际runner/derived SHA的不同含义。

测试使用实际派生函数继续覆盖9/10/11两候选与1/2帧，但让fake peak携带实际window起点或slot，增加断言证明首帧0/shifted上下文/末尾补帧来源以及已有尾前帧未被EOF重推结果覆盖，避免stub仅按fid造相同值而掩盖覆盖错误。无须新增冗余抽象或产品开关。重新运行定向检查/语法/diff check，更新自己的output/SHA后暂停。

## 两处执行前收口

当前复用/EOF实现符合收敛方案。仅删 canonical_json_sha 的 default tolist/str 兜底：当前features实际接口是Python dict/list与数值，未知对象应显式失败，不能悄悄转字符串。将派生compile的filename设为预定 output/derived_observe.py（只构造Path，不提前mkdir），结束时仍保存同源字节，便于实际绑定可追溯。定向6项/语法/diff重新检查，更新output SHA即可；其它不扩展，仍不跑媒体模型。

## 第1轮真实结果后的报告收口

两真实候选已由主控在MPS串行完成，runtime/C-short-native与C-short-shifted；均真实EOF5400，selected原IDs0..5399完整/相同PTS，两候选people_features SHA相同，selected_people均与旧dual控制一致。native识别53.246284791s、1800calls/5400input/5400miss0hit；shifted52.131550125s、1801/5403/5400miss3hit；人物均900图225calls/7170boxes，native内部native/shifted各5400，shifted内部native3/shifted5400，但最终selected两参数都是5400真观测。旧dual97.745275167s、3599/10797、same production SHA，非本轮新测，成本只是不同轮次单次观察。

主控取舍：两候选当前均不采用，不改生产、不补其他场景。native raw缺5300ms/新增10768ms，export500后缺5300/新增11768；shifted raw缺3167/新增2900，export缺4167/新增2900。native新增输出105600–115667；shifted缺原首段7700–10800并把91500–103000延到105900。都是算法输出差异，无匹配人工标签不能叫真实漏失/误报或准确率失败。两单组方向只本次候选未保留，不外推所有单组设计。

现在只读现存runtime与明确primary旧dual镜像，不重跑媒体/模型。新增小summarize.py复用08A compare_intervals/resource_summary（不复制），生成所属正式报告README/summary.json，保留所有raw/export数组、并集缺/增与具体段、调用/缓存/选人/飞行轨迹数、source/helper/derived/runner及媒体/权重SHA/真实来源镜像、单次阶段/采样资源及限制。不同回合数不按zip强配对；原dual没存逐点，不伪称做了全逐点对照。原生实际窗口及selected流在runtime保存可核验，不复制整份几MB逐帧观察进正式报告。

按review-video-results固定数据格式准备 modules/models/tracknet/.runtime/opt09a-single-review.json 与正式报告review.json字节副本：C-short duration180000.3125ms、media_offset_ms=0，video绝对primary原片路径；三行prediction：dual原双组/native基础单组/shifted错位单组，无truth。用raw实际区间；primary_track=shifted；issues6–12秒、39.5–46秒、103–117秒，名字说明输出差异不假造人工判断。可以先README写viewer检查待主控执行，完成报告脚本/数据与副本SHA、语法/diff check后更新自己的output并暂停；主控会实际播放、截图后追加记录再冻结。不要自造HTML。

## 报告来源路径修正

主控发现当前正式summary.viewer_evidence仍写 /tmp/opt09a-artifacts/viewer.json 和 /tmp/opt09a-artifacts/report/review.json。临时验证位置不能当正式证据来源。请在真实worktree用 require_escalated 正常运行 summarize.py，不覆盖REPORT/VIEWER_SOURCE等模块全局，不把临时投影复制后保留错误path；确认正式summary所有本轮source/destination都指真实工作树，review副本与module sidecar同SHA。当前D真实测量占用模型，报告JSON处理可执行，不跑测试/模型。更新自己的output说明实际命令和SHA，仍保持viewer pending到主控实播后记录；不修正为编造已看。完成暂停。

## 主控固定viewer实播记录与最后收口

D当前对照已经完成，当前没有其它模型。主控在固定viewer实际播放C源6.018→12.020秒，三条时间轴同步；随后点击原双组时间轴定位8.135秒，界面显示dual/native保留、shifted删除。此为局部差异定位，不是人工回合起止或全片复核。原生未编辑截图已保存primary绝对路径 /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/opt09a-single/viewer.png。

把截图逐字节复制到正式report/viewer.png并校验SHA/大小，在README与summary.viewer_evidence/summarize.py中替换pending为实际播放/定位记录及上述限制；补图片相对链接与SHA，不覆盖任何原始run。source/report路径必须是真实worktree/primary路径，不能残留tmp投影。修改只报告脚本/文档，语法及diff检查即可，无需重跑6项或模型。更新自己的output/SHA并暂停，之后冻结。
