# 第1轮开发交付

在 `codex/opt06-scan` 独立 worktree 按输入完成诊断脚本和定向检查。本轮未运行真实视频或模型。

## 文件与校验值

- `scan.py`：`2e124af70f90188608b8d8a6aa2b5c6114f05971c9d755e5901f48bb0746766f`
- `test_scan.py`：`2dbed51036f957f2bbb395202798f458c528565b48debd75b1c026b240c6bde9`

脚本要求从 worktree 根目录运行，显式传入清单、案例、缓存权重目录、参照 JSON 和新输出目录。它校验输入视频与权重哈希、MPS 和导入源码路径后，按源 PTS 每秒推理首三张相邻帧，完整读到 EOF；尾部不足三帧只记实际帧信息。覆盖按采样帧时间与 `[start_ms, end_ms)` 区间逐帧计算，并单独报告原始预测和导出区间。

## 已执行检查

- `.venv/bin/python -B -m pytest docs/ai/opt06-scan/test_scan.py -p no:cacheprovider`：2 项通过，覆盖每秒仅首组三帧、邻接帧、末尾不足三帧、阈值等于 0.5、半开时间区间及无采样区间。
- `git diff --check` 与两个新增文件的 `git diff --no-index --check`：通过。

## 主控检查后的补齐

报告现记录 worktree 绝对路径、只读 `git rev-parse HEAD` 和通过 worktree 路径校验的三个实际模块 `__file__`。每段覆盖新增 `hit_timestamps_ms`；测试另外核对低分但有采样时最大分数仍保留，以及扩展区间才命中的情况。补齐后上述定向测试和差异检查已重跑通过。

## 第2阶段：候选窗口计算

新增 `candidate_windows.py` 和独立定向测试 `test_candidate_windows.py`，未修改第1阶段文件。脚本从三份已完成扫描报告读取正例帧，只调用 `modules.media.video.probe` 获取片长、首PTS及分辨率；没有运行模型或完整视频解码。已将扫描报告原样复制到报告目录，并以 SHA-256 核实副本与来源字节一致。

- 候选结果：`apps/video-clipper/reports/opt06-scan/candidate-coverage.json`，SHA-256：`bd701d02e452703441ec7055936b2bd4fa4ed403e4f788942e85b1b2d343a98a`
- `candidate_windows.py`：`dbaffeb8a6b613ab9d04e9f6f744c817dcad9ad21a0b3c61518a5cbbdfa5c2d7`
- `test_candidate_windows.py`：`c3534f014041ec80a82c103dda500235fc38705c17028c95fc00a52b48c9c0f8`
- A-short 扫描报告副本：`b0a438e59ead9c86f5d9165c98c8962f0db7379eab2f6679c066390d74c0bc1f`
- C-short 扫描报告副本：`b4f1a858d6657919d570253af7f3c30c40e358dc6c4e3afc91c273733d2bcfab`
- D-short 扫描报告副本：`c1c776db5ab54b932a4b856adb01ccc6d32ef17f4aa0f9b098d9125e5a08ada2`

`.venv/bin/python -B -m pytest docs/ai/opt06-scan/test_candidate_windows.py -p no:cacheprovider`：2 项通过，覆盖正例扩展的边界裁剪、相接区间合并与未覆盖子区间。`git diff --check` 及新增文件差异检查通过。候选覆盖数据待主控按数据决策；本阶段未实际跳过任何分析。

## 第3阶段：A 候选成本下限 replay 入口

新增 `replay_tracknet.py` 和 `test_replay_tracknet.py`。入口支持 `full` 与 `candidate`，candidate 固定读取 A-short 3000ms 扩展候选；两者完整读取同一源视频并按原始帧号分成不重叠三帧组，只记录执行组起始ID和窗口计数，不保存球点。它复用第1阶段 `scan.py` 的 ROOT 与 SHA helper，并校验本 worktree 导入、MPS、输入及缓存权重；模型由主控串行运行，本轮未运行模型或视频。

- `replay_tracknet.py`：`c0a122ca6b9f03e7d28970d73c31245087ed8f28bd973a9b0224beec080ff02e`
- `test_replay_tracknet.py`：`1d8c9849ebb232d51a36601ee50c812be437cbf69a698ff0b2cc284021a27266`
- `.venv/bin/python -B -m pytest docs/ai/opt06-scan/test_replay_tracknet.py -p no:cacheprovider`：2 项通过，覆盖半开区间边界、组内任一实际帧命中及相邻组不拼接。
- `git diff --check` 与新增文件差异检查：通过。

该入口只测省略回合判定和下游分析后的 TrackNet 成本下限；报告不会生成识别结果或准确率结论。模型准备和完整 EOF replay 墙钟分开记录，TrackNet 分项作为嵌套统计保留。

## 第1轮最终报告与收口

按主控收口输入完成正式证据复制、`apps/video-clipper/reports/opt06-scan/README.md` 和 `task.md` 状态修正。full、candidate 报告均逐字节复制并核对SHA；原版 A recognition_wall 取自保存的 baseline `run.json` 精确值 35.655003875 秒。当前粗查加固定候选不采用；独立验收待进行。没有在收口中重跑视频或模型。

最终定向测试：`.venv/bin/python -B -m pytest docs/ai/opt06-scan/test_scan.py docs/ai/opt06-scan/test_candidate_windows.py docs/ai/opt06-scan/test_replay_tracknet.py -p no:cacheprovider`，6 项通过。`git diff --check` 与本次新增文档/JSON文件的差异检查通过。
