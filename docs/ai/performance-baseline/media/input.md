# 第一轮媒体准备输入
先读../task.md、根AGENTS/README、datasets/README/test-videos.md、curate技能及acquisition。只写本通信output.md和worktree apps/video-clipper/.runtime/performance-baseline/media/，不读developer/verifier通信，不修改实现/标注/既有素材/原outputs。
按技能先status/rally-status。run.py可能初始化独立venv，技能既有requirements的安装已获本任务媒体准备授权，但只在本worktree技能环境或runtime环境写，不改原环境；可复用既有Python3.11依赖减少安装。不得联网搜/下载新来源。
按task制作3长片streamcopy保留音轨，3短片从原目录只读。6输入做完整音视频解码、FileFrameSource EOF、SHA/实际视频元数据；新长片做来源帧像素/相对PTS映射检查(不能仅记录要求窗口)。实际查看连续性证据图并检查场地/机位/跳切；解码成功不等于内容连续。不要将短片拼接或循环成长片。坏输入保留证据回报主控，不擅自换窗口。
保存稳定media/inputs.json，六项case_id/scene/video/court(null)/源窗口、SHA、实际metadata及全部预检证据/状态，供runner使用。新长输入只在worktree忽略目录，无需改tracked manifest，最后主控同步正式清单。不得运行模型推理/基准。

## 主控第一轮源窗口裁定
接受流复制产生的实际窗口：A-long 599.96–1500.04s，C-long 115.07–1020.007s，D-long 0–610.979s。用户要求约15分钟/约10分钟、流复制保留原帧与音轨，方案明确冻结实际源映射，未要求精确非关键帧切点；C前多约4.93s属于已授权制作方法的实际边界，不另行重编码/精确裁切。清单必须同时记录requested_window与actual_window及原因，不能将115.07写成120。此裁定只解除窗口长度差异疑问，不等于全部预检passed；仍需完成来源像素/PTS校验和连续性实际查看后再标passed。
源映射只需验证选定窗口及邻近关键帧，不要求把45/69分钟全源再次完整解码；六正式输入的EOF/全音视频检查不变。可seek到窗口附近顺序比像素哈希/PTS。

## 主控对来源像素比对的实施建议（不降低标准）
已读取source-mapping.json，视频源/clip的固定PTS差为A599.869s、C114.962s、D-0.133s。可以直接依这个已逐包证明的偏移，对每个clip解码帧的实际PTS找到 source_pts=clip_pts+offset 的源帧，比较规范化 frame.to_ndarray(format="yuv420p") 的密集像素字节SHA256和相邻PTS；不要对含stride padding的原始plane缓冲区做hash，也不要依container时长/平均FPS猜帧号。源seek到expected_first前数秒的关键帧，顺序decode跳过前导帧，再逐个匹配即可；D源从头。将首/尾、总比较帧数、mismatch位置、恒定偏移和命令/script摘要保存到probes。首帧判定用实际PTS，不能以target=0.0 seek未命中误判；已有失败尝试仍保留说明原因。
该方法对应原有完整帧序列/源映射检查，无需新来源或重新编码。全部完成后进行连续性接触表实际查看，最后再写passed索引。

## 并行分工更新
主控已将3长片连续性检查单独派发给continuity角色。你只完成全帧来源像素/PTS比对，不再重复制作接触表/切点扫描。待公共 media/continuity/summary.json 成型，可按task批准读取它和对应证据并合并最终inputs.json，不能在公共证据齐备前先标passed。
