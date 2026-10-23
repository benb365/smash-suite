# 媒体准备结果

六份输入索引 `apps/video-clipper/.runtime/performance-baseline/media/inputs.json` 已完成，可供正式runner读取。短片引用原始只读素材；三个长片位于worktree忽略目录 `clips/`。六项SHA均与公共连续性汇总中的媒体SHA一致，完整音视频解码均退出码0，`FileFrameSource`离线读到EOF，实际交付帧数与容器帧数相符。所有项状态为`passed`。

| 输入 | 容器时长 | FPS | 视频帧数 | 来源窗口/映射 |
| --- | ---: | ---: | ---: | --- |
| A-short | 168.091 s | 25 | 4,200 | 原始 A1-01 短片 |
| A-long | 900.211 s | 25 | 22,503 | A1 packet窗口599.96–1500.04 s；全部22,503输出帧像素哈希与PTS逐帧匹配，偏移约599.869 s |
| C-short | 180.000 s | 29.99995 | 5,400 | 原始 C2 短片 |
| C-long | 905.144 s | 29.98112 | 27,134 | C1 packet窗口115.07–1020.007 s；全部27,134输出帧像素哈希与PTS逐帧匹配，偏移约114.962 s |
| D-short | 250.900 s | 29.99996 | 7,527 | 原始 D2 短片 |
| D-long | 611.112 s | 29.98630 | 18,325 | D1 packet窗口0–610.9791875 s；全部18,325输出帧像素哈希与PTS逐帧匹配，偏移约-0.133 s |

全帧比对按每一输出帧实际PTS加实测固定偏移，定位源解码帧；规范化为`yuv420p`后比较逐帧像素SHA-256，同时检查PTS偏移。A/C/D均无mismatch。解码帧首尾PTS分别为A源599.96/1500.04s、输出0.091/900.171s；C源115.07/1020.107s、输出0.108/905.145s；D源0/611.1125s、输出0.133/611.2455s。C/D的最后解码帧PTS与压缩包窗口末端略有差异，索引分别保留packet层`actual_window_s`和解码层`decoded_frame_pts_s`。逐帧总数、首尾PTS、SHA和偏移见`probes/source-frame-verification.json`；连续压缩包映射见`probes/source-mapping.json`。

主控批准的`continuity/summary.json`对全部六份输入判为passed，索引记录其决定、理由和证据。该检查使用短片约25秒接触表及首尾帧、长片约25秒接触表和1Hz低分辨率候选扫描；不是逐帧人工审阅，也不替代回合效果验收。长片候选点检查认为画面变化来自球员/前景人员活动，未观察到机位、主场或场地切换。

六份视频均为1920×1080 H.264并含一条AAC音轨。具体metadata、SHA和全音视频解码日志位于`probes/preflight.json`与对应`.decode.log`。Curator `status`和`rally-status`均成功，复用了原工作区既有Python 3.11环境。没有安装依赖、联网、下载素材、运行模型或写原始素材。仅写本角色授权的`output.md`和worktree忽略的媒体runtime；没有读写原`outputs/`。
