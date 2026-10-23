# Git 提交核对

- 允许范围：本轮性能优化的人类文档、模型与识别实现、回归测试、性能报告和 AI 证据；仅包含输入清单允许的路径。
- 基线：分支 `codex/performance-first-round`，HEAD `5c946e9e6186d052624ca6f853a62d40f034f6e8`；暂存前索引为空。
- 验收来源：`acceptance-closeout-3` 冻结清单核对到 57 个 SHA，缺失 0、变化 0；未重复运行模型或测试。
- 文件核对：patch/证据与其冻结 SHA 完全一致；产品代码和人类文档未改动；`.venv` 是未跟踪临时符号链接，排除提交。
- 暂存差异：108 个文件，4867 insertions、46 deletions。标准 `git diff --cached --check` 报出已有证据 CSV 的 CRLF 行尾和后端日志末尾空行；未改动这些冻结证据。使用 `core.whitespace=cr-at-eol,-blank-at-eof` 检查通过。
