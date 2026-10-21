# 数据集目录

`datasets/` 保存测试和标注使用的素材、来源清单及标注记录。当前数据根目录是
`badminton-v1/`。

素材清单、人工标注和审核要求见[数据规范](requirements.md)。

```text
badminton-v1/
├── manifests/     来源、采样、审核状态、文件校验值和数据划分清单
├── annotations/   模型标注提案、人工修正、审核结论和标注
└── local/         清单与标注关联的本地文件，以及素材整理工作文件
```

## 当前进展

已有来源清单、人工标注和审核记录；独立来源效果验收及本地数据目录整理仍待完成。相关依据见[审核与整理记录](#审核与整理记录)。

## 素材采集环境

训练素材采集工具 `curate-badminton-training-data` 需要 **Python 3.10+**，其中的 yt-dlp 不支持 Python 3.9。它使用技能目录内独立的 `.venv`，不安装到主项目的共同环境中。

工具创建环境时会查找可用的 Python 3.10+；也可用 `CURATE_PYTHON` 指定解释器路径。准备和调用方法见[素材采集工具说明](../.agents/skills/curate-badminton-training-data/SKILL.md)。主项目使用 Python 3.9 时，这个独立环境仍需保留。

## 现用测试视频

16 个现用回合测试视频的来源、窗口、输入路径、制作参数与预检入口见[视频清单](test-videos.md)。

## local 的作用

`local/` 是数据集的本地材料存储区。这里既有用于算法测试的视频片段，
也有人工检查和标注材料，以及搜索、下载和筛选过程留下的工作文件。
它不是专门保存完整原始录像的目录，也不意味着其中所有文件都需要长期保留。

| 子目录 | 当前用途 |
| --- | --- |
| `source-videos/` | 人工确认后明确要求下载的完整来源录像，按候选编号保存 MP4、下载元数据及校验记录；不等于已验收的连续测试片段 |
| `rally/` | 按样本保存原始帧率测试片段、预览拼图、采集和解码日志、审核记录；同时包含已接受、已拒绝和待检查样本 |
| `ysp/`、`test001/` | 从原 captures/ysp、data/samples 迁入的种子视频和检查附件；标注与 ROI 位于 annotations/seed 下 |
| `previews/`、`rally-review/` | 素材筛选和人工检查使用的预览、截图及检查记录 |
| `frames/`、`clips/` | 球场标注图片、人员标注视频片段；不能把低帧率标注片段直接当作回合算法测试输入 |
| `court-fits/`、`court-proposals/` | 人工检查球场拟合或模型点位提案使用的叠图 |
| `cvat-tasks/`、`exports/` | 标注工具任务包和导出的标注材料；这里的 exports 不是应用剪辑视频的输出目录 |
| `search-results/`、`source-probes/` | 搜索结果和来源可用性探测工作文件 |
| `model-inputs/`、`model-proposals/` | 模型辅助标注过程留下的请求、提案或人工修正原稿；需核对 annotations 中的正式保存记录和引用 |

`rally/` 中的片段来自来源录像截取。既有 `sample-rally` 采集流程会重编码并去掉音频；
也有直接复制原始编码、保留音轨的片段。具体方式以相应校验记录为准，
实际帧率、时间戳和首尾展示帧是否与来源一致需核验，不能仅凭 MP4 格式或文件名判断。
2026-10-15 已按人工确认清理18个拒绝样本的 `clip.mp4`，同目录审核材料及清单决定保留；
这些记录缺少视频是有意清理，具体路径和校验值见[执行记录](reports/local-directory-cleanup-execution-20261015.json)。
完整来源录像、测试片段和低帧率预览不是同一种文件。来源录像未完整下载时，
仍通过清单记录来源及截取窗口。
明确要求完整下载的来源保存在 `local/source-videos/<候选编号>/source.mp4`，保留公开可用音轨及原帧率，
优先直接封装而不重新编码。文件完整性检查不代表已通过机位、跳切或回合标注检查。

## 工程如何使用这些文件

- 回合测试先人工确认来源视频，再截取连续片段；分类及时长目标见
  [测试视频规则](../modules/rally/evaluation.md#回合算法测试视频)。
- 回合素材索引在 `manifests/rally-samples.json`。素材被接受只说明通过适用性检查，
  不等于已有人工回合标注，也不等于已经参加算法实测。
- 回合实验入口在 [modules/rally/experiments/](../modules/rally/experiments/)。
  默认种子输入位于 [local/ysp/](badminton-v1/local/ysp/)；ROI 和人工标注位于
  [annotations/seed/ysp/](badminton-v1/annotations/seed/ysp/)。文件输入入口可以显式传入
  `local/rally/` 下的视频。实际使用情况以运行记录中的视频路径、文件校验值、
  处理帧数和结果为证据，已有实测记录见[回合实验报告](../modules/rally/experiments/README.md#实验报告)。
- 球场和人员数据工具通过清单、标注中的路径和文件校验值引用 `local/` 文件。
  数据校验会检查关联文件是否存在、内容是否一致。
- 常规后端自动化测试使用生成的临时视频、模拟数据或预测器，不能代替对采集视频的
  算法效果实测。

## 审核与整理记录

`reports/` 保存素材筛选、标注审核、人工确认和清理证据，与正式标注及来源清单分开：

- [固定机位素材采集](reports/fixed-camera-rally-samples.md)、[短测试片段准备](reports/m1-short-clips-20261015.md)。
- [A/C 首批标注草稿](reports/m1-partial-rally-annotations-20261015.md)、[A/C 完整回合审核](reports/m1-full-rally-annotations-20261015.md)、[D 组完整回合审核](reports/m1-d-full-rally-annotations-20261016.md)。
- [D 组起点更正](reports/d1-start-correction-20261017.md)、[D 组人工标注复核](reports/d1-annotation-review-20261018.md)。
- [本地材料盘点](reports/local-directory-audit-20261014.json)、[清理提案](reports/local-directory-cleanup-proposal-20261015.json)、[清理执行记录](reports/local-directory-cleanup-execution-20261015.json)。

历史 JSON 内的原路径和校验值保持不变，迁移过程可查[归档的报告迁移清单](../backup/docs/records/report-migration-20261019.json)。

## Git 管理与清理

目录说明、`manifests/` 和 `annotations/` 纳入 Git 管理；`local/` 被根目录
`.gitignore` 排除。排除 Git 仅表示本地存储方式，不表示文件可以统一清理。

清理时先核对清单、标注、审核和实验记录的依赖。测试输入和审核依据需要保留；
已拒绝素材的视频、可重建预览及筛选工作文件可单独评估是否清理，同时保留必要的
来源、拒绝原因和人工决定。不能只凭目录名称或“不被自动化测试读取”判断文件无用。

模型与算法的实验缓存归 `modules/` 中所属模块；应用任务数据和最终剪辑视频归对应应用的执行目录。
用于数据集审核和标注的材料继续随数据集存放。

此次迁移未改视频、ROI 坐标、标注时间戳或审核状态，也不表示既有种子标注已完成新口径复核。
旧路径、文件校验值及历史元数据的原内容见[顶层迁移记录](../backup/docs/records/top-level-migration-20261014.json)。
