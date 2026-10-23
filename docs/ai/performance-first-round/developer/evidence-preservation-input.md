# 集成前保留全部原始证据

只执行本文件机械复制工作，不读其他developer或verifier通信，不改产品/文档/测量内容，不Git暂存/提交，不归档或删除工作目录。完成后停止。

用户已批准实际OPT03/04合入，明确本轮所有测试结果保留。合入完成后按既有工作流归档任务/测量worktree，原性能基线worktree明确必须保留。为防 ignored 原始证据随任务目录消失，需要先将它们按同一相对路径复制到主目录，逐字节保留。源目录当前没有symlink，167+1个文件，总约1.4GiB；没有模型/实验运行中。

只复制这两个路径（源→目标）：
- /Users/bytedance/.codex/worktrees/performance-first-round/smash-suite/apps/video-clipper/.runtime/performance-first-round → /Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/performance-first-round
- /Users/bytedance/.codex/worktrees/performance-first-round/smash-suite/modules/rally/.runtime/performance-first-round → /Users/bytedance/workspace/experiments/smash-suite/modules/rally/.runtime/performance-first-round

检查目标根均不存在才开始，若已有内容停止报告不覆盖。允许创建缺失的上述父目录，目标仍为ignored缓存证据，不进Git。使用保留文件元数据的复制方式，不改任何文件内容/JSON中的历史绝对路径；原输入与权重路径保持。复制后对每个相对文件比较源/目标字节数及SHA256，文件集合一致。不删除源。

允许在任务目录写 docs/ai/performance-first-round/controller/evidence-preservation.json，记录两个映射、每个相对文件的字节与SHA256、总数/总字节、核对结论；该JSON是执行校验索引，不复制视频/大数据进Git。自己的总结写docs/ai/performance-first-round/developer/evidence-preservation-output.md。不要读/改task.md，不启动查看器或模型，不检查outputs/。
