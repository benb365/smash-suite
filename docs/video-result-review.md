# 视频结果展示入口

视频、人工标注与算法区间的查看流程统一使用仓库内的
[review-video-results skill](../.agents/skills/review-video-results/SKILL.md)。
固定网页模板、服务脚本、展示约定、输入数据格式和维护检查均在该 skill 内维护，本文件只保留入口。

准备一份符合[数据格式](../.agents/skills/review-video-results/references/data-format.md)的 JSON，放在相应模型的运行目录，然后执行：

```sh
python3 .agents/skills/review-video-results/scripts/review.py \
  --data models/模型目录/.runtime/本次实验/review.json --port 18770
```

打开终端打印的网址，直接检查视频和时间轴。不为新实验重新生成 HTML、复制播放器代码或重复审计已固定的展示逻辑；只有修改查看器或发现异常时再执行 skill 内的维护检查。

历史实验页及其原始结果保留，后续查看默认使用固定查看器。
