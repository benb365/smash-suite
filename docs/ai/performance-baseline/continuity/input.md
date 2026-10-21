# 第一轮长片连续性复核（机械素材检查）
先读../task.md、根AGENTS、README、curate素材技能及其中视频窗口检查规则。不读developer/media/replay/verifier通信目录，不改源码/标注/既有视频，不联网或下载。
你的任务是并行完成3长片的连续性/固定机位检查，来源帧像素与PTS由媒体角色另做，勿重复。素材只读：
/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/media/clips/A-long.mp4
同目录 C-long.mp4、D-long.mp4。
可读公共media/probes/preflight.json与source-mapping.json，仅了解实际时长/来源；数据检查不涉及回合标注或算法区间展示，无需构建HTML。
仅写 apps/video-clipper/.runtime/performance-baseline/media/continuity/ 下检查脚本/小图/原始日志及summary.json，和自己 docs/ai/performance-baseline/continuity/output.md。
使用既有Python/PyAV/Pillow或FFmpeg，不额外安装。制作间隔约25秒(含首尾)接触表，另以低分辨率全窗场景突变扫描定位候选切点，实际查看接触表和候选点附近图像，检查摄像机切换/编辑跳切/场地与主场变化。保留采样时间、扫描阈值、候选点、实际查看的图及判断，不将抽样表述为逐帧人审。不以解码成功代替连续性。
若发现疑似真实切镜/缺失/机位变化，标blocked并报告，不替换窗口、不剪掉/拼接。若证据显示稳定记录，则标passed并说明适用范围是本轮性能输入的连续性检查、不作回合效果验收。summary.json包含3case_id、video、checks/evidence/decision/reason，供媒体索引合并。脚本只读6输入，CPU工作完成后停止，不能与正式测量并跑。输出后回报停止。