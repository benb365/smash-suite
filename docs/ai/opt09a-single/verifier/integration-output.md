# OPT09A 主目录集成验收

## 结论

集成证据核对通过，可以提交本次 OPT09A 结果。验收接受源任务已有的 shifted 完整 MPS 独立复跑、6 项边界检查和对应代码/报告审查；本轮主目录只做字节、路径、提交范围和文档核对，没有重跑功能测试。

## 本轮实际核对

- 主目录位于 `develop`，提交前 HEAD 为 `5bb39fa69181e86c21bde20e74d951f1cb2ca415`；来源工作树 HEAD 为 `48ffa7e4fc463926e7f11b4930ba83065aed3837`，且来源工作树干净。
- 冻结列出的 17 个原 staged 路径与 index 路径完全相同，index 中各文件 SHA 均匹配冻结记录。feature README 和 roadmap 的工作区副本含额外未暂存改动；本次只提交其原 staged 内容，保留工作区编辑。
- 14 个接受文件均与来源工作树和 preservation manifest 的目标 SHA/字节数相符。task 文档是集成阶段元数据例外：保留来源 SHA，同时目标 SHA/字节数匹配 preservation 清单。21 个 runtime 文件及 2 个 sidecar 的 SHA/字节数全部匹配。
- `modules/rally/recognize.py` SHA 为 `17fb4cfb4387a8394836bc9793e526c42cf139ec291d6ee890a9d09e7052adad`；`modules/models/tracknet/predictor.py` SHA 为 `d8208470e973ff4388d8c34be54f19609a50a61571e72aaa3ed45dcaf8c34152`，与已验收来源一致。没有生产代码的 staged 或 tracked diff。
- 正式报告没有残留 `/tmp/opt09a-artifacts` 路径；报告说明无 SHA 匹配人工标签，truth 轨道省略，差异不是准确率、漏球或误报结论。
- `git diff --check` 与 `git diff --cached --check` 均通过。

## 采用的既有验证与边界

独立验收记录确认实际 MPS shifted C-short 重跑与冻结结果逐值一致，5400 帧达到 EOF，所选 observation/PTS 和模型窗口完整，6 项 9/10/11 与 1/2 帧边界检查通过。该验证来自来源工作树，本轮仅核对保存证据 SHA，不重新执行。

当前 D 性能候选运行期间，按集成输入约束未运行 pytest、模型、前端构建或产品测试。本轮没有新增生产改动，故不声称主目录重新验证功能行为。

## 提交范围

提交仅包含冻结的 17 个 staged 文件，以及本次 `integration-freeze.json`、`verifier/integration-input.md` 和本文件。未加入 runtime、输出目录、ideas 草稿、baseline SVG/文档或其它用户改动；不推送、不归档。
