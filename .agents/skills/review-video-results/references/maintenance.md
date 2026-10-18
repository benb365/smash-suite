# 仅在修改查看器时检查

新实验只准备数据并运行脚本，直接检查网页；不要把以下维护流程变成每次查看的前置任务。

修改脚本、模板或数据格式后：

```sh
python3 -m unittest discover -s .agents/skills/review-video-results/tests -v
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" \
  .agents/skills/review-video-results
git diff --check
```

测试覆盖区间交并与共享输出、原区间保留、确认状态与非法时间、无人工行、HTTP视频范围读取。视频拖动依赖`206 Content-Range`响应，不要退回不支持范围读取的临时服务。

另外只在模板行为变化时实际打开一个已有数据集，检查一次播放/暂停、慢放、色块点击及拖动、视频进度条反向联动、切换视频与问题入口。检查一个真实起点和终点的偏移。存在排除事件时检查独立行；没有人工行时确认不显示人工成绩。

使用已有A1或C1数据即可，不重跑模型、不重新编码视频、不修改标注。模板脚本可用本机Node做语法检查；日常运行不依赖Node、第三方Python包或外部网页资源。

历史实验页保留作为原记录。修复通用行为时只改本skill；除非用户要求，不批量重写旧页或改变旧实验成绩。
