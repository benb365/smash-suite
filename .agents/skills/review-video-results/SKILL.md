---
name: review-video-results
description: Display saved video annotations and algorithm intervals in a local web page with a synchronized player and comparison timelines. Use for visual result review; it does not run models, edit annotations, or export clips.
---

# 视频结果复核网页

直接运行固定查看器，不为每份结果重新编写或生成 HTML。页面模板、服务脚本和数据约定全部维护在本 skill 内。

## 使用

1. 按 [数据格式](references/data-format.md) 准备一份 JSON，放在所属模块的运行目录。复用已保存的实际视频、标注和算法输出；不要为展示修改区间或补造人工确认。
2. 从仓库根目录启动（仅需 Python 3.9+ 标准库）：

   ```sh
   python3 .agents/skills/review-video-results/scripts/review.py \
     --data modules/rally/.runtime/本次实验/review.json --port 18770
   ```

   直接使用终端打印的本机网址。端口已占用时保留现有服务，改用 `--port 0` 自动分配空闲端口。Ctrl-C 停止；数据更新后重启命令并刷新网页。
3. 用可用的浏览器工具打开该网址并展示。直接检查实际视频能否播放、一个起止位置是否对齐、切换视频是否正常；随后交给用户查看，并提供链接。使用支持保留标签页的工具时保留该页。

日常只换数据和视频、执行命令、打开检查。脚本自动做基本输入检查，不要求每次重算评估、核对全部区间、重新写页面、录制截图或跑展示代码测试。用户要求额外验证或发现具体异常时再查。浏览器工具自身要求截图时照其要求执行。

## 展示约定

已确认的[时间轴参考图](assets/reference-timeline.png)随本 skill 保存；示例区间不代表实际数据。

- 播放器与等比例时间轴联动，点击/拖动时间轴和视频进度条、播放暂停、调速、切换视频保持同步。
- 人工确认回合为绿色；第一种算法结果为蓝色，第二种为灰色；更多方案保留独立名称和颜色。已确认排除事件单列橙色。缺少人工标注时不补造绿色区间或算评估成绩。
- 默认播放完整视频，允许模拟所选方案的剪辑；逐回合起止对照、少留对打、多留间歇、问题入口均使用同一份输入。
- 输入时间统一为毫秒、相对于测试片段首帧。视频播放时间 = 输入时间 + `media_offset_ms`，偏移来自真实首帧时间，不猜帧率、不改标注来对齐。
- 正式评估数字由数据的 `summary` 原样展示。表格只计算区间交并以帮助定位，不另做模型判断或替代正式评分；查看和播放不代表审核通过。

## 维护

只在修改本 skill 的脚本、模板或数据契约时运行 [维护检查](references/maintenance.md)。不要回到历史实验目录复制旧模板或新增一次性页面生成脚本。

独立脚本位于 [scripts/review.py](scripts/review.py)，固定页面位于 [assets/index.html](assets/index.html)。[回合实验文档](../../../modules/rally/experiments/README.md#查看视频与结果)提供发现入口，不另维护一套规则。
