# 第四轮：报告表格单位
用户要求“表格的单位标注一下”。在原worktree /Users/bytedance/.codex/worktrees/performance-baseline/smash-suite 继续，先git status，HEAD应为15182e8。只读本input与报告，不读其他角色通信。仅修改apps/video-clipper/reports/performance-baseline.md的5张数值表表头，其他正文/数值/图表/索引/程序不变。
正式结果表：录像时长与准备/识别/成片/总耗时列明确（秒），处理速度明确（倍），成片段数明确（段）。识别主阶段各时间列明确（秒）。资源表统一RSS（GiB）、CPU峰值（%）、MPS allocated / driver（MiB）、最大间隔（秒）。Python表接收/collected、可见入口、残余均（样本），展开错误（次）。原生表所有时间（秒），CPU混合列明确样本（个）/权重（秒），MPS混合列明确事件（条）/配对裁剪并集（秒）；PID/UID是标识符无物理单位。非数值链接表不添加单位。表头中文自然、尽量简短；不要改变任何数据单元格。
检查全部7表列数一致、所有数据行与HEAD逐字相同、git diff --check。只写报告与自己的correction/output-units.md（简短记SHA/改动/检查），不提交不推送不采样不鉴权。完成停止写入交主控独立复验。无需创建或更新402文件完整清单，主控用HEAD+本次单文件SHA冻结。
