# OPT08C 第1轮开发输出

起点为 commit c62527982a6bcd6fc95cb00572f346d52d36fffb，分支 codex/opt08c-gray；pyproject.toml 与主目录哈希均为 955e99f299a8c932ead4e23384266750056a1be0531aec393641cb23ff446822。复用了主目录已安装的 .venv，没有安装依赖。

已准备：

- run.py 提供 color9、gray9、gray3 三种完整 A-short 识别变体。它复用 OPT-08A 尺寸 runner 的完整识别、统计、采样与权重/媒体校验；将 helper 的 288×512 尺寸派生入口替换为灰度派生，识别导入前绑定实际候选类。输出注明 helper 层标签、实际变体、输入通道、代码类路径、源/派生/runner 哈希，并保存派生源码。gray3 的首层折叠函数在加载 CPU 权重后、eval.to(device) 前调用。
- probe.py 仅在收到明确执行命令后采样 A-short 前缀；每组从目标时间之后首个 frame_id 能被3整除的帧开始，收集连续三帧。它准备核对媒体/缓存权重 SHA、固定 MPS、实际线程数、图像 SHA、三类实际模型输入、首层输出和热图张量指标、points/candidates、gray9/gray3 输入复制关系以及所有非首层 state key 哈希。完成第三组即停止迭代，明确不检查 EOF；不保存图像或完整热图。
- test_experiment.py 使用合成张量、合成帧与 stub model；不读取媒体或权重。

运行入口示例（实际模型运行尚未执行，输出目录需不存在）：

.venv/bin/python docs/ai/opt08c-gray/probe.py \
  --inputs apps/video-clipper/reports/performance-first-round/inputs.json \
  --models apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models \
  --output apps/video-clipper/.runtime/opt08c-gray/probe

.venv/bin/python docs/ai/opt08c-gray/run.py \
  --variant gray3 --case A-short \
  --models apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models \
  --output apps/video-clipper/.runtime/opt08c-gray/A-short-gray3

定向检查 pytest -p no:cacheprovider -q docs/ai/opt08c-gray/test_experiment.py 通过（5项）；py_compile 和 git diff --check 通过。测试覆盖当前派生的三种颜色路径、同一折叠函数的首层通道分组与偏置/其他参数保持、实际 CPU 图像预处理的通道与时间顺序/源图未变、前缀取样的模3起点和连续帧。合成卷积仅用数值容差检查浮点运算，不代表真实权重数值等价。

## 真实执行前最小修订

- `run.py` 的首层折叠在 detach 前保存原 `requires_grad`，替换后的 Parameter 保留该属性；折叠测试分别覆盖 True/False。
- 移除 runner 中未使用的临时目录与文件，并合并重复 helper 加载逻辑；两次调用仍创建独立模块实例。
- `probe.py` 在导入项目模块前将当前 worktree 根目录插入 `sys.path`。它会校验 FileFrameSource、生产 predictor、TrackNet 和 assets 的实际源码路径均位于本 worktree，且生产 predictor 精确匹配当前路径；路径和源码 SHA 写入 probe 结果。
- 本轮重新执行上述 5 项定向测试、三个脚本的 `py_compile` 和 `git diff --check`，全部通过。未运行真实模型、权重或媒体。

## 实际执行结果与报告收口

主控已完成真实数值 probe 和 gray3 A-short 全片识别；本轮只读取并汇总既有数据，没有重新运行模型、权重或媒体。`summarize.py` 复用 OPT-08A 的区间、点差和资源汇总函数，正式报告位于 `apps/video-clipper/reports/opt08c-gray/`。

- 数值 probe 三组共九帧。gray9/gray3 对应模型输入通道复制严格相等；除首层 weight/in_channels 外 state 一致。首层最大绝对差 5.7220459e-6，三组 heatmap 最大绝对差约 5.96e-7、3.76e-7、2.20537e-6，默认 `torch.allclose` 均为 False。九个点 x/y 相同、五个 confidence 不同；九个采样帧中六个 candidate 列表不同。
- 完整识别完成 EOF：两次记录均为 4200 帧、1400 次模型调用。gray3 单次识别墙钟 25.0091 s；原色 OPT-08A 288×512 主目录镜像控制 29.9666 s（不同轮次的单次观察）。原始区间和 padding 500 ms 后的导出区间均有 840 ms 控制区间未覆盖、240 ms 新增；这不是人工确认的漏检或误检。
- 原色控制派生源码镜像 SHA 为 `01b5d8274b743807e5bc10a4992b6ec66a3bd58f77236a9ccd376a2fe69ef9f9`，gray3 派生源码 SHA 为 `5c94de392d70e91cb3a23cb4acbdf51ae6735fe4d94c3f5bfbb63825eca8fd80`；生产 predictor 源 SHA 相同，为 `d8208470e973ff4388d8c34be54f19609a50a61571e72aaa3ed45dcaf8c34152`。
- 主控 viewer 播放源视频 3.000–11.020 s 后定位 3.715 s；该单帧显示原色行保留、gray3 行删除。此为局部边界证据，没有人工标注起止或全片复核。
- 决策记录为本轮不采用 gray3，不继续本方案生产化，不补跑 C、不改产品，也不否定其他灰度方案。没有匹配人工标签，效果保持尚未证明。
- 冻结前修订已将 summary 的 viewer 状态改为实际播放记录，并注明未做人工标注/全片复核。helper `runner_sha256` 标为继承的 OPT-08A runner；另列实际 OPT-08C runner SHA `953059bc6aa4f99b9b65f9e29e135e61275f8512d97eb75b959aa19e5e42b214`。README 提供相对链接到 summary、probe、review 和 viewer 截图。

`probe.json`、`review.json`、`viewer.png` 已逐字节复制到正式报告目录并核对长度和 SHA；`summary.json` 从原始 runtime 结果独立计算，未覆盖原运行数据。summarize.py 的语法检查通过；第一阶段 5 项定向测试及 py_compile 已通过。

SHA256：

- run.py: 953059bc6aa4f99b9b65f9e29e135e61275f8512d97eb75b959aa19e5e42b214
- probe.py: abc07320928acd36b8440d0a6ddfe2c074ace1f3180ac6cc390b6e3596a8737b
- test_experiment.py: 5950b34d15c442615a2c5711822695ef5fdc6c0f6124260074a8bbded67fc48b
- modules/models/tracknet/predictor.py: d8208470e973ff4388d8c34be54f19609a50a61571e72aaa3ed45dcaf8c34152
- summarize.py: b66d285a592ea7e29beaa11cc349b2afc0f9247e5405d33ab4f81c2398c26f20
- apps/video-clipper/reports/opt08c-gray/README.md: 8710392f80f255e295ced7660ec4d03c1d763df814bec4a2c63016b8d316bcd9
- apps/video-clipper/reports/opt08c-gray/summary.json: 92bb36fa4a4215f8cc0c540af394ecb4447bb4fa28b686c1d6cd14f94951824e
- apps/video-clipper/reports/opt08c-gray/probe.json: 97fad4fbf682fef8806f4ad5a9a97234f2f4991cd30305687df1dcc5290a6de1
- apps/video-clipper/reports/opt08c-gray/review.json: 3f826f6a07d2a26555dfd3ac659249601f042ba053780091743b95f71ed115cb
- apps/video-clipper/reports/opt08c-gray/viewer.png: 4bda36ecbca0f258e4635f8b1148a0a5fd21b0a96e1604cd9d4409aa61aaf6dd
