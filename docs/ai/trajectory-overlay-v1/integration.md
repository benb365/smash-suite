# 二维球路首版集成

用户于 2026-10-23 明确要求合入 develop。沿用用户停止自动独立复核、人工查看样片的安排；本次只执行必要工程集成检查，不补造最终独立视觉验收结论。

## 范围与状态

- 集成任务分支的二维球路分析、球点记录、A 场景默认开启且可关闭的球路选项、成片小球场及箭头烧录、对应测试与文档。
- 路线图 15/16 保持用户指定的“演进中”，移除本次首版认领。高远球精度与其他场景支持继续在 feature 优化文档维护。
- develop 中其他未提交修改单独保留，不纳入本次提交。不推送远程。

## 证据保存

归档前将任务 worktree 的最终及历史成片、叠图、逐拍结果、球点/人物缓存保存到主目录下的相同相对路径，逐文件核对 SHA256。清单见同目录 `evidence-preservation.json`。

主目录已有修改的恢复副本位于 `.runtime/trajectory-integration/backup-before-preparation/`；实际安装集成提交前另保存当时最新版本，以保留并行编辑。

## 工程检查

源功能提交：`37a0123`；集成基线：`41ad27d`。在以该 develop 提交为第一父提交的集成分支进行合并，当前无源码合并冲突。

- 完整后端：`.venv/bin/python -m pytest -q -p no:cacheprovider`，148 项通过，1 条既有 Starlette/httpx 弃用提示。
- 前端：使用已安装工具依次执行 `tsc --noEmit`、`rspeedy build`、`rsbuild build --config host.config.ts`，均通过。
- 文档：已安装 `vitepress build` 通过；`git diff --check` 通过。
- 日志保存到主目录 `.runtime/trajectory-integration/checks/`。未重跑追球/人物模型，未启动新的功能或视觉复核。

为与主目录正在编辑的文件分析优化共存，球点记录跳过“未计算窗口”的非有限分数标记，并增加对应回归测试。实际模型输出仍按原规则记录，不将跳过标记写成球点。

主目录其他未提交改动按三方内容合并保留，恢复副本和合并预览保存在 `.runtime/trajectory-integration/`。这些其他任务的改动不属于本次功能集成提交。
