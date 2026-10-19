# 固定机位单打 Rally 样本采集报告

日期：2026-10-03。用途：Smash Suite 非商业本地算法验证。

## 当前结果

已本地筛选 12 个独立固定机位单打片段：6 个官方赛事高视角、6 个个人/校园/球馆录像。合计 36.00 分钟，视频文件约 655.8 MiB。每段约 180 秒，原始帧率 25–30fps；11 段为1080高，1段为720p。双打不计入本轮。

**尚未确认个人组的手机拍摄设备**：6段个人组均标记设备未知。它们满足固定机位单打视频条件，但不能宣称已完成“6个有手机设备证据”的子目标。此前有手机描述的来源分别因双打、手持移动或变焦被排除。保留来源和设备证据字段，避免把个人上传等同于手机拍摄。

本轮完成素材采集和适用性检查，未在新片段上运行分割算法、未标注回合边界、未修改 TrackNet 分割算法。因此，这份报告不代表跨场景准确率已经验证。

## 入选视频

每个链接可打开本地原始帧率片段。窗口使用源视频时间（秒）；片段自身从0秒计时。

| 组别 | 样本与来源 | 源窗口 | 分辨率 / 原始fps | 本地片段 | 特征与局限 |
|---|---|---|---|---|---|
| 官方 | [【回放】女单 明地阳菜vs王祉怡1/16赛 2026全英羽毛球公开赛 清流](https://huya.com/video/play/1098784534.html) | 600–780 | 1920×1080 / 25 | [official-allengland-2026-court3](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/official-allengland-2026-court3/clip.mp4) | 高视角固定全场，女单连续比赛，包含擦场与较长暂停。 |
| 官方 | [【回放】男单	冲本优大VS希莫加 2026加拿大羽毛球公开赛 清流](https://huya.com/video/play/1116089984.html) | 600–780 | 1920×1080 / 25 | [official-canada-2026-court2](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/official-canada-2026-court2/clip.mp4) | 高视角固定全场，男单连续比赛，含多回合与等待。 |
| 官方 | [【回放】女单	安洗莹vs黄宥薰 2026印度羽毛球公开赛 清流](https://huya.com/video/play/1091949210.html) | 600–780 | 1920×1080 / 25 | [official-india-2026-court3](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/official-india-2026-court3/clip.mp4) | 高视角固定全场，女单连续比赛；联系表有短暂压缩花屏，作为画质挑战保留。 |
| 官方 | [【回放】女单 邱品蒨vs碧查梦 1/16赛 2026奥尔良羽毛球大师赛 清流](https://huya.com/video/play/1100833780.html) | 600–780 | 1920×1080 / 25 | [official-orleans-2026-court2](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/official-orleans-2026-court2/clip.mp4) | 高视角固定全场，女单连续比赛，含多回合与等待。 |
| 官方 | [【回放】男单 周天成vs奈良冈功大 1/16赛 2026新加坡羽毛球公开赛 清流](https://huya.com/video/play/1110867874.html) | 600–780 | 1920×1080 / 25 | [official-singapore-2026-court2](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/official-singapore-2026-court2/clip.mp4) | 高视角固定全场，男单连续比赛，含多回合与等待。 |
| 官方 | [【回放】女单 瓦尔达尼vs黄玲青 1/8赛 2026瑞士羽毛球公开赛 清流](https://huya.com/video/play/1099925376.html) | 600–780 | 1920×1080 / 25 | [official-swiss-2026-court3](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/official-swiss-2026-court3/clip.mp4) | 高视角固定全场，女单连续比赛，含回合间等待与擦场。 |
| 个人/球馆 | [20261001 羽毛球业余单打低视角 友vs超](https://www.bilibili.com/video/BV16kaz6fEQz/) | 120–300 | 1920×1080 / 29.97 | [personal-20261001-singles](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/personal-20261001-singles/clip.mp4) | 固定后场低斜角业余单打，连续比赛及捡球/发球等待；行人多次遮挡画面，作为遮挡挑战保留。拍摄设备未知。 |
| 个人/球馆 | [羽毛球业余单打练习赛 vs昱哥 20230215 p01 第一局](https://www.bilibili.com/video/BV1pk4y1Y7XB/) | 60–240 | 1906×1080 / 29.99 | [personal-BV1pk4y1Y7XB-v2](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/personal-BV1pk4y1Y7XB-v2/clip.mp4) | 固定后场低角度业余单打，有相邻场活动和短暂前景经过，设备未知。 |
| 个人/球馆 | [羽毛球真棒！一场精彩的羽毛球单打比赛！！！](https://www.bilibili.com/video/BV1Z64y1W7dJ/) | 120–300 | 1280×720 / 29.97 | [personal-club-exhibition-stable](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/personal-club-exhibition-stable/clip.mp4) | 固定低斜角球馆单打表演赛，保留回合间停顿，720p，设备未知；避开片头转场。 |
| 个人/球馆 | [大学生羽毛球爱好者21分单打对局完整记录](https://www.bilibili.com/video/BV1KB4y1S7u1/) | 120–300 | 1920×1080 / 29.97 | [personal-college-21points](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/personal-college-21points/clip.mp4) | 固定后场校园单打连续对局，多个回合及准备/捡球，设备未知。 |
| 个人/球馆 | [低视角 "稳重心，赢一半"男子羽毛球单打 民间男单单打视频](https://www.bilibili.com/video/BV16t421t7Qw/) | 145–325 | 1920×1080 / 29.97 | [personal-jiangmen-stable](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/personal-jiangmen-stable/clip.mp4) | 固定低斜角民间单打，多个回合及换边，设备未知；避开原窗的相机调整。 |
| 个人/球馆 | [100zz单打](https://www.bilibili.com/video/BV17D4y147F6/) | 120–300 | 1920×1080 / 30 | [personal-qianfoshan-singles](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally/personal-qianfoshan-singles/clip.mp4) | 固定低角度球馆单打，近侧边界局部裁出画面，保留为低机位挑战，设备未知。 |

## 本地核查方法

- 保留连续有界窗口，不拼接回合；每个场馆/机位只计一次。
- 逐帧完整解码，记录原始fps、尺寸、时长、文件SHA-256；原帧率低于24fps时失败，不插帧凑数。
- 每5秒生成一张缩略图用于观察场地、球员、比赛与等待；疑似切镜点另行检查。画面变化分数只提示可疑变化，并不能证明机位稳定。
- 对换边/小幅移动存在疑问的片段增密提帧，检查背景与时间连续性。例如小董片段约119.5–120秒突然换边，即使场景检测未提示切镜也不入选。
- 入选包含低角度、近侧场地局部裁出、相邻场活动、行人遮挡、擦场/较长暂停等。官方组可做清洁基线；个人组暴露实拍困难，不应只看两组汇总。
- 未做版权或许可证核验；保留来源URL及核查记录。仅使用公开、无需登录的下载入口。

## 排除与未完成记录

下表为已经下载但排除的片段；它们仍保留诊断，不进入12个主测试样本。

| 样本 | 原因 |
|---|---|
| official-worlds-2023 | Contact sheet and 18 cut flags show player profiles, close-ups and spectators; not a continuous fixed-camera match window. |
| personal-jiangmen-native-v2 | 原取窗内有机位调整，改用145–325s独立取窗；同机位不重复计数。 |
| phone-yuzi-native-v2 | 双打，不属于当前固定机位单打范围。 |
| phone-xjtu-freshmen | 手机单打录制有持续移动/倾斜机位，不计入固定机位。 |
| personal-BV1sJKP6qEVt-v2 | 单打个人录制有变焦和转动机位。 |
| official-malaysia-2026-court2 | 双打，且原窗口大部分为暖场，不计入单打范围。 |
| personal-BV1Z64y1W7dJ | 原取窗有暖场到比赛的转场，改用120–300s；同机位不重复计数。 |
| official-malaysia-2026-court2-play | 双打，不属于本轮单打范围。 |
| personal-beijing-womens-final | 背景比较确认跟拍转动和倾斜机位，不能计入固定机位。 |
| phone-momota-play | 新取窗仍有变焦、观众远景、特写及转动机位，不合格。 |
| personal-cuhksz-stable | 更密的背景比较发现机位漂移/倾斜，主场近边界不全，未纳入固定机位主测试集。 |
| personal-amateur-match | 持续转动/倾斜机位且前景遮挡，不能计入固定机位。 |
| personal-dong-singles | 100–130s密集提帧确认119.5–120s附近突然换边，未保留连续比赛时间轴，不计入主测试集。 |
| personal-tennis-player-singles | 训练到比赛转场且机位变化，有剪辑，不是连续固定单打窗口。 |
| personal-qaq-singles | 教学剪辑穿插文字页、跳剪和变焦，不是连续比赛窗口。 |
| personal-japan-highschool | 来源描述为转载优酷；TV特写和转场频繁，不是个人固定机位。 |
| personal-school-games | 联系表确认随着运动员转动机位，不计入固定机位。 |
| official-asia-2026-court2 | TV回放内有多个特写、重播和镜头切换，不计入固定机位。 |

下载失败及尚未复核的片段见独立清单，不能作为合格数量。公开 YouTube 多个来源要求登录确认，未使用 cookies；部分 Bilibili 来源没有返回可用视频格式，保留失败诊断，未无休止重试。

## Skill 与运行资源

仓库现有采集skill已增加独立的Rally测试模式，复用下载、时间窗、文件校验等基础设施；原球场/人物训练标注流程仍保留。新增模式不要求人工球场点标注，也不将素材通过等同于回合标注通过。

- `sample-rally`：公开来源或本地视频→约3分钟原始帧率片段→全解码检查→缩略图。
- `review-rally`：记录适用性、设备证据和理由，和既有人工场地/来源审批分开存储。
- `rally-status`：只统计单打；同时报告官方、个人和有手机证据的机位数量。
- 依赖：Python 3.10+、yt-dlp 2026.8.19及curl-cffi、FFmpeg、imageio-ffmpeg；使用skill自有虚拟环境。
- 下载与完整解码流程使用CPU及网络，不需要GPU或额外的视频理解API；视觉复核由当前助手完成。主测试片段存储大小如上；诊断与淘汰片段额外占空间。
- 13项采集测试通过，Skill结构校验通过，差异空白检查通过。最终校验日志已保存在本地。

## 使用入口与下一步

- [样本清单](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/manifests/rally-samples.json)（包含源URL、时间窗、原始fps、尺寸、SHA-256和适用性理由）。
- [本地素材目录](/Users/bytedance/workspace/test/smash-suite/datasets/badminton-v1/local/rally)。每个样本目录有clip.mp4、contact.jpg、sample.json、decode.log。
- [采集 Skill](/Users/bytedance/workspace/test/smash-suite/.agents/skills/curate-badminton-training-data/SKILL.md)。
- [算法现有实测报告](../../modules/rally/experiments/reports/tracknet-rally-segmentation.md)。

下一轮用现有算法逐个处理12段单打，先查看实际区间和轨迹，找出漏完整回合、误把捡球识别成比赛、遮挡导致回合拆碎等失败。根据真实失败修改算法。手机设备证据继续单独补齐，不把设备未知写成已证实；当前样本已可用于个人录像场景测试。
