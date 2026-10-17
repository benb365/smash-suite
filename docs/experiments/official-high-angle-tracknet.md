# 官方高视角固定机位单打：本地 TrackNet 实测

2026-10-03。按用户要求，只跑已采集的六段官方高视角单打；不处理个人组，不训练或下载新模型，不修改算法。

**六段各180秒，18分钟视频全部逐帧处理，输出34个候选片段。算法在部分机位上能分开回合，但抽查已发现短回合漏检和还球/准备动作误报，不能认定为跨机位稳定可用。** 原样片11个回合的结果不能推广为本批准确率。

模型推理循环累计787.43秒（约13.12分钟），整体约1.37倍播放速度；每段1.25–1.45倍。本机Apple GPU/MPS，复用已有Python环境和约43.3MiB权重。计时包括视频解码、模型、分割和日志，不包括模型加载及预览编码；预览并行处理，因此不是隔离负载的性能测试。没有调用云端模型。

## 六段实际输出

输入均1920×1080、25fps、4500帧；均为来源第600–780秒的连续窗口。表内“段数”是模型候选数，不是确认正确回合数。

| 样本 | 候选数 | 推理循环耗时 | 播放速度倍率 | 片尾模型仍处于回合状态 | 轨迹预览 |
| --- | ---: | ---: | ---: | --- | --- |
| 印度公开赛 | 8 | 136.93s | 1.31× | 否 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/h264/trajectory-preview.mp4) |
| 奥尔良大师赛 | 4 | 143.62s | 1.25× | 否 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-orleans-2026-court2/h264/trajectory-preview.mp4) |
| 新加坡公开赛 | 5 | 126.63s | 1.42× | 否 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-singapore-2026-court2/h264/trajectory-preview.mp4) |
| 全英公开赛 | 6 | 131.00s | 1.37× | 是 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-allengland-2026-court3/h264/trajectory-preview.mp4) |
| 加拿大公开赛 | 5 | 125.29s | 1.44× | 否 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-canada-2026-court2/h264/trajectory-preview.mp4) |
| 瑞士公开赛 | 6 | 123.97s | 1.45× | 是 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-swiss-2026-court3/h264/trajectory-preview.mp4) |

全英和瑞士在输入结束时仍有已确认状态，沿用原算法“不强行在文件结束处结束回合”的规则，没有导出对应的未完成区间。输入窗口可能截断原始回合，不能从这180秒恢复窗口外的部分。

[全部片段导航和区间跳转](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/preview.html) · [机器汇总](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/summary.json) · [抽查记录](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/visual-review.json)。

## 已观察到的效果和问题

| 样本/片内时间 | 实际观察 | 算法输出及诊断 | 证据 |
| --- | --- | --- | --- |
| 印度 约16–19秒 | 发球后短回合，随后比分11:9变11:10 | 无输出覆盖。15.76秒出现候选，19.12秒过期，始终未确认。 | [抽查图](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/missed-point.jpg) |
| 印度 约58–62秒 | 上一回合结束后走动、捡球/还球和准备，未见新比分变化 | 额外输出57.52–62.28秒，疑似间歇误报。原截图文件名split-point仅为检查时名称，复看结论是疑似还球误报。 | [抽查图](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/split-point.jpg) |
| 奥尔良 约68–79秒 | 约68–73秒对打，随后还球和准备 | 真实对打没有输出；随后输出75.60–79.44秒。68.92和70.92秒的候选分别过期，75.88秒候选却在78.00秒确认。 | [抽查图](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-orleans-2026-court2/missed-and-return.jpg) |
| 全英 约22–25秒 | 极短发接发，比分10:9变11:9 | 无输出覆盖；这3秒约2.7%的帧通过追球有效条件，没有帧通过运动条件，追球失败也是原因。 | [抽查图](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-allengland-2026-court3/missed-point.jpg) |
| 全英 约9–12秒 | 取球、还球和等待，比分保持10:9 | 输出8.76–12.12秒，疑似间歇误报。 | [抽查图](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-allengland-2026-court3/ball-return.jpg) |
| 新加坡 约35–41秒 | 实际发球后对打，约40秒附近结束 | 输出36.60–40.04秒，前后补时的34.60–41.04秒片段覆盖所抽查的准备和结束。 | [抽查图](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-singapore-2026-court2/short-rally-end.jpg) |
| 加拿大 约66–70秒 | 抽查第二段末尾，对打结束后走动 | 裁剪59.44–69.96秒覆盖所抽查的结束过程；比分稍后才更新。 | [抽查图](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-canada-2026-court2/rally-end.jpg) |
| 瑞士 约47–75秒 | 47–56秒对打后近端球员倒地，随后等待、擦场 | 输出47.08–56.48秒，没有把随后长暂停连接进去。比分约75秒才更新。 | [抽查图](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-swiss-2026-court3/long-rally-end.jpg) |

上述为助手画面与轨迹抽查，未建立完整逐回合精确人工标签，因此不报告准确率、召回率或完整漏检/误报总数。比分只用于核对事件，未进入算法；比分更新可以明显滞后于球落地，不能用它直接替代结束边界。新加坡和加拿大各5个输出的顺序与各5次比分变化相符，仍不等于所有起止边界都正确。

## 为什么失败

1. 现有分割器依赖有效连续飞行，要求至少2.2秒才确认。短回合或追球断续会让真实对打候选过期：印度、奥尔良的候选都没有到达确认状态。
2. 还球也是真实的球运动，能通过置信度、速度和持续时间条件。只判断“球在运动”不能可靠区分双方对打与间歇；单纯放宽确认时长还会增加这种误报。
3. 全英漏检位置首先缺少有效追球，不能归因于时长一个参数。输入被现有模型缩到512×288，小球、背景和机位差异可能影响检测；这是待验证假设，本轮没有通过改模型、裁图或调参来证明原因。

下一轮直接用这些已发现的失败位置验证改进：先改善真实对打的追球连续性及极短回合保留，再增加区分双方对打与还球的信号。场地裁图、其他追球模型或球员击球动作属于待选实验分支，本轮没有实施；不把继续扩充素材或收紧评测要求作为算法迭代的前置条件。

## 实际复用的技术

复用 `backend/app/vision/tracknet_rally.py` 的本地TrackNet模型适配器与分割器，以及 `RallyStream` 逐帧契约。三张连续帧拼成9通道，模型输入512×288；热图置信度0.6，运动速度按1920px画宽基准100–4000px/s，运动窗口80–200ms，三次连续运动观察，静默1.6秒结束、飞行跨度2.2秒确认。

唯一视角配置差异：旧运行脚本读取旧样片的verified ROI；新六段没有场地标注，本轮使用既有 `FlightConfig()` 的完整画面范围 `(0,0,1,1)`。没有套用旧球场坐标，没有自动球场检测，也没有新增模型裁图。时间、速度、置信度参数与现有候选相同；空间范围不同需在比较时明确。

现有seed脚本的结果保存器绑定旧人工标签。本轮本地批处理适配器复用该脚本的推理/预览函数，替换结果保存和视角配置入口，不读取或套用旧标签。正式代码、旧seed结果、权重、源视频及采集清单未改。

## 查看和重现

脚本与所有输出位于 `/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003`。

```bash
/Users/bytedance/workspace/test/smash-suite/models/SoloShuttlePose/.venv/bin/python /Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/run_official.py --device mps
```

`inputs.json` 保存六份来源记录；每段目录有 `inference.json`、`rallies.json`、逐帧追球与诊断JSONL、抽查图，以及 `h264/trajectory-preview.mp4` 和逐回合MP4。`run.log` 保存实际处理记录，`render_previews.py` 和日志保存导出与编码验证；`preview.html` 提供候选区间跳转和片段入口。

补时仍是前2秒、后1秒，与算法首末飞行区间分开。所有时间均基于本地180秒片段；转换到来源录像时间加600秒。

## 验证

- 六段完整处理27000帧；模型输出、诊断行数与帧数一致，没有降帧或新增下载。
- 独立重放六份保存轨迹，预测区间和诊断逐字段与模型运行完全一致；没有使用未来帧，三帧组在末帧到达后处理。
- 六段配置一致，原片、权重、算法与轨迹哈希匹配；输出记录未替换原始标签。
- 全部6段H.264轨迹预览及34个候选片段解码、帧率/帧数与区间检查通过；预览均180秒、4500帧、25fps。
- 本轮没有改产品行为，因此没有重复后端单元测试；实际全片运行和重放记录见[校验汇总](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/final-validation.json)和[日志](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/final-validation.log)。

## 原始预测区间

以下为未经人工修正的算法输出，不含补时。

### 印度公开赛

来源：[原录像](https://huya.com/video/play/1091949210.html)；[原始JSON](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/rallies.json)。

| 候选 | 观察飞行区间（秒） | 裁剪区间（秒） | 片段 |
| ---: | --- | --- | --- |
| 1 | 0.72–3.84 | 0.00–4.84 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/h264/rally-01.mp4) |
| 2 | 27.92–32.24 | 25.92–33.24 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/h264/rally-02.mp4) |
| 3 | 48.80–53.92 | 46.80–54.92 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/h264/rally-03.mp4) |
| 4 | 57.52–62.28 | 55.52–63.28 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/h264/rally-04.mp4) |
| 5 | 71.04–89.76 | 69.04–90.76 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/h264/rally-05.mp4) |
| 6 | 105.76–108.92 | 103.76–109.92 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/h264/rally-06.mp4) |
| 7 | 126.68–131.24 | 124.68–132.24 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/h264/rally-07.mp4) |
| 8 | 147.44–162.68 | 145.44–163.68 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-india-2026-court3/h264/rally-08.mp4) |

### 奥尔良大师赛

来源：[原录像](https://huya.com/video/play/1100833780.html)；[原始JSON](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-orleans-2026-court2/rallies.json)。

| 候选 | 观察飞行区间（秒） | 裁剪区间（秒） | 片段 |
| ---: | --- | --- | --- |
| 1 | 22.08–46.36 | 20.08–47.36 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-orleans-2026-court2/h264/rally-01.mp4) |
| 2 | 75.60–79.44 | 73.60–80.44 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-orleans-2026-court2/h264/rally-02.mp4) |
| 3 | 90.72–106.96 | 88.72–107.96 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-orleans-2026-court2/h264/rally-03.mp4) |
| 4 | 125.20–129.16 | 123.20–130.16 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-orleans-2026-court2/h264/rally-04.mp4) |

### 新加坡公开赛

来源：[原录像](https://huya.com/video/play/1110867874.html)；[原始JSON](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-singapore-2026-court2/rallies.json)。

| 候选 | 观察飞行区间（秒） | 裁剪区间（秒） | 片段 |
| ---: | --- | --- | --- |
| 1 | 14.44–27.08 | 12.44–28.08 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-singapore-2026-court2/h264/rally-01.mp4) |
| 2 | 36.60–40.04 | 34.60–41.04 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-singapore-2026-court2/h264/rally-02.mp4) |
| 3 | 62.20–66.52 | 60.20–67.52 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-singapore-2026-court2/h264/rally-03.mp4) |
| 4 | 81.00–94.52 | 79.00–95.52 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-singapore-2026-court2/h264/rally-04.mp4) |
| 5 | 105.96–134.48 | 103.96–135.48 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-singapore-2026-court2/h264/rally-05.mp4) |

### 全英公开赛

来源：[原录像](https://huya.com/video/play/1098784534.html)；[原始JSON](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-allengland-2026-court3/rallies.json)。

| 候选 | 观察飞行区间（秒） | 裁剪区间（秒） | 片段 |
| ---: | --- | --- | --- |
| 1 | 1.32–4.20 | 0.00–5.20 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-allengland-2026-court3/h264/rally-01.mp4) |
| 2 | 8.76–12.12 | 6.76–13.12 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-allengland-2026-court3/h264/rally-02.mp4) |
| 3 | 99.84–113.56 | 97.84–114.56 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-allengland-2026-court3/h264/rally-03.mp4) |
| 4 | 135.72–139.96 | 133.72–140.96 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-allengland-2026-court3/h264/rally-04.mp4) |
| 5 | 142.68–146.12 | 140.68–147.12 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-allengland-2026-court3/h264/rally-05.mp4) |
| 6 | 156.64–159.72 | 154.64–160.72 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-allengland-2026-court3/h264/rally-06.mp4) |

### 加拿大公开赛

来源：[原录像](https://huya.com/video/play/1116089984.html)；[原始JSON](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-canada-2026-court2/rallies.json)。

| 候选 | 观察飞行区间（秒） | 裁剪区间（秒） | 片段 |
| ---: | --- | --- | --- |
| 1 | 41.88–44.96 | 39.88–45.96 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-canada-2026-court2/h264/rally-01.mp4) |
| 2 | 61.44–68.96 | 59.44–69.96 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-canada-2026-court2/h264/rally-02.mp4) |
| 3 | 83.16–89.16 | 81.16–90.16 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-canada-2026-court2/h264/rally-03.mp4) |
| 4 | 102.28–111.60 | 100.28–112.60 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-canada-2026-court2/h264/rally-04.mp4) |
| 5 | 137.40–176.48 | 135.40–177.48 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-canada-2026-court2/h264/rally-05.mp4) |

### 瑞士公开赛

来源：[原录像](https://huya.com/video/play/1099925376.html)；[原始JSON](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-swiss-2026-court3/rallies.json)。

| 候选 | 观察飞行区间（秒） | 裁剪区间（秒） | 片段 |
| ---: | --- | --- | --- |
| 1 | 3.64–15.28 | 1.64–16.28 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-swiss-2026-court3/h264/rally-01.mp4) |
| 2 | 28.20–31.36 | 26.20–32.36 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-swiss-2026-court3/h264/rally-02.mp4) |
| 3 | 47.08–56.48 | 45.08–57.48 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-swiss-2026-court3/h264/rally-03.mp4) |
| 4 | 101.04–109.04 | 99.04–110.04 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-swiss-2026-court3/h264/rally-04.mp4) |
| 5 | 112.32–114.72 | 110.32–115.72 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-swiss-2026-court3/h264/rally-05.mp4) |
| 6 | 142.36–153.80 | 140.36–154.80 | [播放](/Users/bytedance/workspace/test/meterials/outputs/official-high-angle-20261003/official-swiss-2026-court3/h264/rally-06.mp4) |
