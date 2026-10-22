# OPT09A 第1轮开发补记

本次按“真实执行前最小修订”更新了入口与定向测试，没有改产品代码、旧 helper 或 08C/其他实验文件。

`run.py` 现在预先绑定实际 TrackNet predictor 子类及记录 wrapper，再调用既有 `docs/ai/opt07a/recognition.py` 的 `main()`，透传为 `candidate/C-short`；模型校验、资源采样、统计、失败文件及预测结果由 helper 执行。外层不预建 output 目录，保留并恢复 `sys.argv`。完成或失败后将本候选的 derived source、观察数据及元数据补入 helper 输出；run.json 分开记录 helper runner 与 OPT09A runner、derived observe 的 SHA。入口将当前任务 ROOT 无条件置于 `sys.path[0]`。

派生 observe 仅替换正常 phase 条件与最终返回选择。原 target、首窗 seed、EOF真实末组恢复均保留；native 选择 `{**shifted, **native}`，保证 native 优先并由真实 shifted tail 补缺，shifted 选择 shifted。两个下游流共享同一 `rows` 列表，不新增 phase 字段。Predictor 仅记录帧 ID、点与候选数量；所选原始观测保存在 observations.json。

定向测试使用真实 observe 源派生的假帧执行 9/10/11 帧两候选及 1/2 帧边界。fake peaks 携带真实模型调用窗口起点和槽位，断言首帧、shifted上下文、EOF尾帧来源，并确认 N=10 中原普通窗口已观测的 frame 8 没有被 EOF 重算覆盖。

执行前收口：规范 JSON SHA 不再把未知对象兜底转字符串；派生函数编译使用预定的 `output/derived_observe.py` 路径，落盘字节与被执行源码一致。

验证结果：`pytest -p no:cacheprovider -q docs/ai/opt09a-single/test_experiment.py`：6 passed；使用外置 pycache 的 `py_compile` 通过；`git diff --check` 通过。一次默认 py_compile 尝试因工作树禁止写入实验目录的 `__pycache__` 失败，改用 `/tmp/opt09a-pycache` 后检查通过。未运行媒体、模型、权重或全量测试。

本轮真实运行命令仍由 helper 驱动，入口参数示例：

```sh
.venv/bin/python docs/ai/opt09a-single/run.py \
  --variant native \
  --inputs apps/video-clipper/reports/performance-first-round/inputs.json \
  --models apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models \
  --output apps/video-clipper/.runtime/opt09a-single/C-short-native
```

SHA256：

- `run.py`: `de947ebac22f020347cca1be775b6294acdb7c38dbf69b5f7f4b9dfe8bb1ec20`
- `test_experiment.py`: `a367c852784d5fe1ec9986c46cbf707f9786d587521eb07ae1a059a4dd31b61d`

## 第1轮真实结果报告收口

未重跑模型。汇总脚本读取本轮 native/shifted runtime，以及主目录中经 OPT-07A preservation 清单逐文件 SHA 核验的旧双组 C-short 保存镜像；通过 `docs/ai/opt08a-size/summarize.py` 复用并集区间比较和资源汇总，没有把不同回合数按顺序强行配对。报告包含三方案完整 raw/export 区间、每段并集缺失/新增区间、诊断、人物/轨迹/模型工作量、采样资源、环境及输入/权重/实际源代码/runner/derived SHA。双组镜像没有逐窗口预测点，报告明确不做逐点比较。

两候选都完整到达 EOF 5400 帧；selected IDs 为 0–5399，PTS相同；people feature SHA相同，选中人物与双组一致。native / shifted 的 TrackNet 调用分别为 1800 / 1801，输入帧 5400 / 5403，cache miss/hit 为 5400/0 与 5400/3。与旧双组区间并集比较：native raw 缺 5300 ms/新增 10768 ms，export 缺 5300 ms/新增 11768 ms；shifted raw 缺 3167 ms/新增 2900 ms，export 缺 4167 ms/新增 2900 ms。遵照保守门槛，两候选均不采用；这些仅是算法输出变化，没有 SHA匹配人工标注，不能称为真实漏失、误报或准确率结果。

正式材料：`apps/video-clipper/reports/opt09a-single/README.md`、`summary.json`、`review.json`。查看器 JSON 按固定 schema 保存到 `modules/models/tracknet/.runtime/opt09a-single-review.json`，视频时长为指定的 180000.3125 ms，与正式报告副本逐字节相同；未声明 truth 行，差异窗口只作定位。viewer 播放和截图仍待主控执行。本轮未生成 HTML、未重跑媒体/模型。

本轮检查：汇总脚本 `py_compile` 通过，三个 JSON 可解析，review JSON及正式副本 SHA 一致，`git diff --check` 通过。汇总逻辑在 `/tmp` 临时重定向输出执行，防止绕过当前工作树写入限制；生成文件通过工作区补丁写入指定 worktree。实际 SHA：`summarize.py` `6edabeabdf2bb99fd50332fdb71b3da46b30218ec8668d3ad7ac54b9c2c75b69`；`summary.json` `4e416bfdc73fee93405b1e37a2c496d17f5fe9ce26d8a1ae1838b720e92644d8`；`review.json` 与 runtime viewer JSON 均为 `0f8ae1a032f1e2b8f74154ccdd0d9d3225824b20c2a08e351b11415715178aa1`；README `0a7b5b32d5d6ee6c3c23df014111d825a07017f7bc2fb33ab102b268919d685b`。

## 报告来源路径修正

按指定使用提升权限直接执行 `.venv` 外的系统 Python 命令 `python3 docs/ai/opt09a-single/summarize.py`，重新从已保存 runtime 生成正式文件；未运行测试、视频或模型。现在 summary 的 viewer source 和 report copy 均指向真实 OPT09A worktree；summary 中无 `/tmp/` 引用。module sidecar 与正式副本字节相同，SHA 均为 `d2aa45541d848472d657bc39aa3c1c9f7baecf7cb6653db71ca90089216883f4`。viewer 状态仍是等待主控实际播放与截图，没有宣称已看。

修正后 SHA：`summarize.py` `6edabeabdf2bb99fd50332fdb71b3da46b30218ec8668d3ad7ac54b9c2c75b69`；`summary.json` `6080cd268ad9725c90779bede4b99ebd2740c94309ee29acca31b4760030f2d6`；`review.json` 与 module sidecar 均为 `d2aa45541d848472d657bc39aa3c1c9f7baecf7cb6653db71ca90089216883f4`；`git diff --check` 通过。

## 主控 viewer 实播记录收口

按要求将 primary runtime 原始截图 `/Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/opt09a-single/viewer.png` 逐字节复制至正式报告 `apps/video-clipper/reports/opt09a-single/viewer.png`。源与副本大小均为 92688 bytes、SHA256 均为 `297f2654578570d55fc15443424ba9f2d46b61253e29d891c9fe52a0452bafef`。

`README.md` 与 `summary.json` 已记录主控实播：C源 6.018–12.020 秒三条时间轴同步；点击 dual 时间轴 8.135 秒时界面显示 dual/native 保留、shifted 删除。记录明确这是局部差异定位，不是完整视频复核或人工回合边界标注。summary 的 screenshot 来源/目的均为正式路径，review JSON 来源与副本路径也均为真实 worktree；没有 `/tmp/` 引用。truth 行仍省略，准确性状态没有伪造。

按要求实际运行 `python3 docs/ai/opt09a-single/summarize.py` 更新文档和summary；仅执行 `py_compile` 与 `git diff --check`，未跑测试、媒体或模型。最终 SHA：`summarize.py` `0e073dae4299a526ea979924c306fa60ed0d99b556b6de50b16c1d58a026f3d0`；`summary.json` `f98f76470b77361c24eb0e22b2de7a6c0d8ab16fa0ad18e791f2d23b23b57802`；`README.md` `a125caebe81619deb7fa0c7e3e153cfd732511171a2f1974c6c5e45f38855d92`；`review.json` `d2aa45541d848472d657bc39aa3c1c9f7baecf7cb6653db71ca90089216883f4`；`viewer.png` `297f2654578570d55fc15443424ba9f2d46b61253e29d891c9fe52a0452bafef`。
