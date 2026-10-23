# 媒体读写

读取视频信息和带时间戳的图像帧，或按给定时间区间生成连续音视频。不负责判断回合，也不依赖产品后端。

## 调用

先按[项目首页](../../README.md#开发环境)安装共同环境。以下示例在仓库根目录执行：

```python
from pathlib import Path
from modules.media.video import probe, render, selected_ranges
from modules.media.video_input import FileFrameSource

source = Path("input.mp4")
info = probe(source, source.name)
with FileFrameSource(source, mode="offline") as frames:
    for frame in frames:
        # frame_id、timestamp_ms、image（BGR 图像）
        pass

ranges = selected_ranges([{"start_ms": 1000, "end_ms": 5000}], info.duration_ms)
render(source, Path("output.mp4"), ranges, info, "balanced", lambda fraction: None)
```

产品如需烧录字幕叠图，可传 `overlay_ass=Path("overlay.ass")`。媒体模块在既有选段与时间变换之后应用 ASS，不读取叠图内容，也不依赖产品或羽毛球算法模块。

`selected_ranges` 默认不补时；调用方可传 `padding_ms`。导出保留源画面尺寸和原音画相对偏移，支持 `high`、`balanced`、`small` 三档质量。调用者负责输出目录和工作文件的生命周期。

## 输入预检

更换测试视频后，先用应用实际使用的 `FileFrameSource` 完整读到文件结尾，再运行模型。以下命令在仓库根目录执行；将示例路径替换为待检查文件，也可追加多个路径：

```sh
.venv/bin/python - input.mp4 <<'PY'
import json
import sys
from modules.media.video_input import FileFrameSource

for path in sys.argv[1:]:
    with FileFrameSource(path, mode="offline") as frames:
        for frame in frames:
            pass
    print(json.dumps({"path": path, "status": "passed", **frames.stats}, ensure_ascii=False))
PY
```

必须无截断地迭代到结尾；不要设置 `limit_s`、提前退出，或把所有图像存入列表。所有文件都输出 `passed` 且命令退出码为 0，才算通过。输出记录实际解码数、交付数、容器声明帧数及首尾时间；容器声明了非零帧数时，完整解码数必须与之相等。解码错误、损坏帧、无效时间戳或尺寸变化也会导致失败。

此命令只检查视频帧，不运行模型，也不验证音轨；音视频完整解码和来源对应检查仍按[素材获取说明](../../.agents/skills/curate-badminton-training-data/references/video-acquisition.md#verify-media)执行。

## 帧与时间

`TimestampedFrame` 和 `VideoInfo` 定义在 `types.py`。帧包含递增且流内唯一的整数 `frame_id`、源时间轴上的毫秒时间戳 `timestamp_ms` 和当前图像 `image`。时间戳必须有限且严格递增，图像像素格式由输入适配器统一。

`FileFrameSource` 用 PyAV 解码原始 BGR 图像，以首帧 PTS（视频帧的显示时间戳）为零点保留实际帧时间间隔；缺失、重复或回退的时间戳会报错，不按估计帧率伪造时间或补帧。源分辨率和帧率保持不变。

`offline` 尽快读取；`realtime` 按单调时钟的启动时刻加源时间调度，模拟文件原速输入。一个解码线程与一个消费者之间最多排队六帧；实时模式下，最旧排队、待提交或正在处理帧落后计划时刻超过默认五秒，终止分析并保留诊断，可用 `max_lag_s` 调整。离线模式只施加有界阻塞，不使用实时超时。

固定帧率诊断适配器 `iter_cfr_video_frames` 仅用于数据清单明确声明恒定帧率的文件：时间戳为零起点帧号除以清单帧率，抽样不重编号。可变帧率或真实采集源应提供实际源时间戳。

文件模拟的墙钟延迟与回合结果的源时间分别记录，不包含真实设备在采集、编码或网络传输中的耗时。当前没有摄像头或网络接入适配器；这些来源可以沿用同一帧输入约定。

## 实验记录

文件输入、实时模拟、持续运行和分辨率对照的历史实测见[输入模块实验](experiments/realtime-input.md)。记录对应当时的环境和代码。

## 当前进展

文件读写、逐帧输入和区间导出已实现；既有自动检查通过。真实摄像头或网络流适配尚未接入，目标负载下的长片性能仍待验证。整理后的入口检查记录见[快速检查说明](../../docs/ai/2026-10-19-quick-check/notes.md)。

## 测试

```sh
.venv/bin/python -m pytest modules/media/tests
```

依赖 PyAV、OpenCV、NumPy、Pydantic；编码使用系统 FFmpeg 或 `imageio-ffmpeg`，也可通过 `SMASH_SUITE_FFMPEG` 指定程序。
