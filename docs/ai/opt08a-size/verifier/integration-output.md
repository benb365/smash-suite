# OPT-08A 主目录集成验证

轮次：第 1 轮。已验收来源提交 `a960998b367aea63ca2f10e01059be9e3c542614`；主目录集成前 HEAD `0467b6590d16e4dc60ecc3ae6aa0a40063da8b51`。

## 核对结果：通过

- 集成冻结清单 18 个暂存内容 SHA 全部匹配；19 个原暂存路径均处于两个 OPT-08A 目录或允许的性能优化 README、roadmap 范围。没有产品代码或其它路径。
- 保存清单中的 14 个验收文件、22 个原始运行/独立证据文件、1 个 TrackNet review sidecar 和 2 个 viewer 文件均核对大小与 SHA，来源及主目录副本一致。`task.md` 只包含已授权的主控状态更新；源 worktree HEAD 为 `a960998b367aea63ca2f10e01059be9e3c542614` 且干净。
- 规划 index 只记录本轮两种缩小尺寸不采用及后续 OPT-08C 认领。working tree 中用户的 ideas、optimization-details、README/roadmap 改稿、SVG 和 outputs 均保持未暂存。
- 定向检查：`test_run.py` 的 3 项测试全部通过；`git diff --cached --check` 和 `git diff --check` 通过。
- 正式报告和机器汇总一致：288×512 控制输出匹配已保存的 OPT-07A 候选；216×384 与 144×256 改变了输出。没有匹配人工标签，报告未将差异声称为准确率或真值损失；两种缩小尺寸均按保守门槛不采用，未追加 C-short、未改产品实现。

本次没有运行模型或视频解码，没有更改实现、报告内容、标准或用户工作区草稿。集成验证范围与报告的单次成本观察及未验证限制一致。
