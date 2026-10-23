# 现用回合测试视频

## 视频清单

下表是 16 个现用诊断样本的视频入口；A、C、D 分别选择产品中的比赛高视角、场边低视角、个人斜侧方。
样本用于从实际视频重新运行[场景识别](../modules/rally/README.md#运行场景算法)。旧保存观测检查所需缓存现已缺失，其专用入口已移除；获取视频不会恢复旧模型观测。
已有文件优先复用；缺失时按[素材整理技能](../.agents/skills/curate-badminton-training-data/SKILL.md)获取原片并制作片段。

时间单位为秒，范围左含右不含，表示原视频中的位置。片段路径相对于
`badminton-v1/local/rally/`；完整原片保存在 `badminton-v1/local/source-videos/`。
表中链接指向现用片段，不是原片。原片按 `badminton-v1/local/source-videos/<来源编号>/source.mp4` 保存；C2 使用同目录下的 `source-full.mp4`。

| 样本编号 | 来源 URL | 原视频范围（秒） | 已有片段 |
| --- | --- | --- | --- |
| A1-01 | [A1][source-a1] | [599.96, 767.96) | [m1-short-a1-01-20261015/clip.mp4](badminton-v1/local/rally/m1-short-a1-01-20261015/clip.mp4) |
| A1-02 | [A1][source-a1] | [1200.04, 1374.04) | [m1-short-a1-02-20261015/clip.mp4](badminton-v1/local/rally/m1-short-a1-02-20261015/clip.mp4) |
| A1-03 | [A1][source-a1] | [1800.12, 1974.12) | [m1-short-a1-03-20261015/clip.mp4](badminton-v1/local/rally/m1-short-a1-03-20261015/clip.mp4) |
| A1-04 | [A1][source-a1] | [2346.16, 2514.2) | [m1-short-a1-04-20261015/clip.mp4](badminton-v1/local/rally/m1-short-a1-04-20261015/clip.mp4) |
| A2-01 | [A2][source-a2] | [600, 696.84)¹ | [m1-a2-01-20261019-workerfix/clip.mp4](badminton-v1/local/rally/m1-a2-01-20261019-workerfix/clip.mp4) |
| A2-02 | [A2][source-a2] | [698.88, 780)¹ | [m1-a2-02-20261019-workerfix/clip.mp4](badminton-v1/local/rally/m1-a2-02-20261019-workerfix/clip.mp4) |
| C1-01 | [C1][source-c1] | [120.073, 285.1743125) | [m1-short-c1-01-20261015/clip.mp4](badminton-v1/local/rally/m1-short-c1-01-20261015/clip.mp4) |
| C1-02 | [C1][source-c1] | [1200.55, 1380.6603125) | [m1-short-c1-02-20261015/clip.mp4](badminton-v1/local/rally/m1-short-c1-02-20261015/clip.mp4) |
| C1-03 | [C1][source-c1] | [2400.217, 2565.5863125) | [m1-short-c1-03-20261015/clip.mp4](badminton-v1/local/rally/m1-short-c1-03-20261015/clip.mp4) |
| C1-04 | [C1][source-c1] | [3600.152, 3775.2583125) | [m1-short-c1-04-20261015/clip.mp4](badminton-v1/local/rally/m1-short-c1-04-20261015/clip.mp4) |
| C2 | [C2][source-c2] | [120, 300) | [personal-qianfoshan-singles-restored/clip.mp4](badminton-v1/local/rally/personal-qianfoshan-singles-restored/clip.mp4) |
| D1-01 | [D1][source-d1] | [0, 150.989125) | [m1-short-d1-01-20261015/clip.mp4](badminton-v1/local/rally/m1-short-d1-01-20261015/clip.mp4) |
| D1-02 | [D1][source-d1] | [150.989125, 305.97825) | [m1-short-d1-02-20261015/clip.mp4](badminton-v1/local/rally/m1-short-d1-02-20261015/clip.mp4) |
| D1-03 | [D1][source-d1] | [305.97825, 455.9674375) | [m1-short-d1-03-20261015/clip.mp4](badminton-v1/local/rally/m1-short-d1-03-20261015/clip.mp4) |
| D1-04 | [D1][source-d1] | [455.9674375, 610.9458125) | [m1-short-d1-04-20261015/clip.mp4](badminton-v1/local/rally/m1-short-d1-04-20261015/clip.mp4) |
| D2-01 | [D2][source-d2] | [0, 250.9003125) | [d2-check-20261018/clip.mp4](badminton-v1/local/rally/d2-check-20261018/clip.mp4) |

[source-a1]: https://huya.com/video/play/1099925376.html
[source-a2]: https://huya.com/video/play/1091949210.html
[source-c1]: https://www.bilibili.com/video/BV12zPKzRE4v/
[source-c2]: https://www.bilibili.com/video/BV17D4y147F6/
[source-d1]: https://www.bilibili.com/video/BV1QPpz6pEJJ/
[source-d2]: https://www.bilibili.com/video/BV1mz4y1J7DK/

¹ A2 的范围以完整原片首个显示帧为零点；原始显示时间戳从 1.48 秒开始。两段之间的损坏区域保持排除，不能拼接成连续素材。
A2 两段分别制作，保留来源帧间隔并用无损 H.264 编码；C2、D2 按来源窗口复制视频流。片段保留来源音轨和音画时间关系。

表中的范围用于定位实际画面，不一定等于剪切命令参数；现用片段制作参数见
[片段制作参数](#test-clip-parameters)，通用获取与校验方法见
[素材整理技能](../.agents/skills/curate-badminton-training-data/references/video-acquisition.md)。
运行识别前，按[完整输入预检](../modules/media/README.md#输入预检)逐一检查现用输入。
这些素材已有诊断用途，不因列入此表而成为独立验收集。

## 片段制作参数

<a id="test-clip-parameters"></a>

以下参数对应上方样本。候选输出应与现用片段分开保存，并按[通用素材检查流程](../.agents/skills/curate-badminton-training-data/references/video-acquisition.md#verify-media)确认映射、音轨和完整解码。

以下命令均从仓库根目录运行。先按[素材整理技能](../.agents/skills/curate-badminton-training-data/SKILL.md)准备独立环境，再设置 FFmpeg 路径并创建候选输出目录。完成后按需执行对应来源的小节：

```bash
CURATOR_PY=.agents/skills/curate-badminton-training-data/.venv/bin/python
FFMPEG_PATH="$("$CURATOR_PY" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
CANDIDATES=.runtime/clip-candidates
mkdir -p "$CANDIDATES/A2" "$CANDIDATES/C2" "$CANDIDATES/D2"
```

### A1/C1/D1

按上文原片路径规则，使用下列 `-ss` 与 `-t` 参数；复制原视频和音频流。通用命令模板见[从本地原片剪切](../.agents/skills/curate-badminton-training-data/references/video-acquisition.md#extract-from-a-local-original)。

| 样本 | `-ss` 秒 | `-t` 秒 |
| --- | --- | --- |
| A1-01 | 599.96 | 167.92 |
| A1-02 | 1200.04 | 173.92 |
| A1-03 | 1800.12 | 173.92 |
| A1-04 | 2346.16 | 167.96 |
| C1-01 | 120.073 | 165.001 |
| C1-02 | 1200.55 | 180.01 |
| C1-03 | 2400.217 | 165.269 |
| C1-04 | 3600.152 | 175.007 |
| D1-01 | 0 | 150.8558125 |
| D1-02 | 150.989125 | 154.8558125 |
| D1-03 | 305.97825 | 149.855875 |
| D1-04 | 455.9674375 | 154.8450625 |

### A2

先将 A2 原片从 MPEG-TS 封装为 MP4 并保留原始 PTS（显示时间戳），再按上表窗口分别制作无损 H.264 片段，并保留原音轨：

```bash
A2_SOURCE=datasets/badminton-v1/local/source-videos/A2/source.mp4
A2_REMUX="$CANDIDATES/A2/source-remux.candidate.mp4"

"$FFMPEG_PATH" -y -hide_banner -nostdin -v warning -copyts \
  -i "$A2_SOURCE" -map 0 -c copy -avoid_negative_ts disabled \
  "$A2_REMUX"
while read -r start duration name; do
  "$FFMPEG_PATH" -y -hide_banner -nostdin -v warning -ss "$start" \
    -i "$A2_REMUX" -t "$duration" \
    -map 0:v:0 -map 0:a:0 -c:v libx264 -qp 0 -preset ultrafast \
    -pix_fmt yuv420p -bf 0 -fps_mode passthrough -enc_time_base demux \
    -c:a copy -avoid_negative_ts make_zero \
    "$CANDIDATES/A2/$name.candidate.mp4"
done <<'EOF'
600 96.84 A2-01
698.88 81.12 A2-02
EOF
```

### C2

复制 C2 原视频和音轨；`-ss` 与 `-t` 是剪切命令参数，实际输出跨度不必等于上表范围长度：

```bash
C2_SOURCE=datasets/badminton-v1/local/source-videos/C2/source-full.mp4
"$FFMPEG_PATH" -y -hide_banner -nostdin -v warning -ss 120 \
  -i "$C2_SOURCE" -t 179.90 -map 0 -c copy \
  "$CANDIDATES/C2/C2.candidate.mp4"
```

### D2

复制 D2 原视频和对应音轨，指定 7527 个视频帧；`-t` 是命令参数，不保证与实际输出时长完全相同：

```bash
D2_SOURCE=datasets/badminton-v1/local/source-videos/D2/source.mp4
"$FFMPEG_PATH" -y -hide_banner -nostdin -v warning -i "$D2_SOURCE" \
  -map 0 -c copy -frames:v 7527 -t 250.9003125 \
  "$CANDIDATES/D2/D2.candidate.mp4"
```
