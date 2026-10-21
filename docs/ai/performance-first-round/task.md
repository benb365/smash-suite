# 首轮性能优化任务

## 授权与版本
- 2026-10-21 用户明确授权：按细化方案实施，两条开发线并行，先分别验证四项，再组合有效改动。无需重新询问已确认范围。
- 基线提交：5c946e9e6186d052624ca6f853a62d40f034f6e8，任务目录：/Users/bytedance/.codex/worktrees/performance-first-round/smash-suite，任务分支 codex/performance-first-round。
- 已批准方案：docs/features/performance-optimization/first-round.md；效果边界见该专题README。主目录已有ideas、outputs及规划文档修改，不回退、不提交这些主目录内容。
- 用户后续明确本轮暂缓批处理，OPT02产品改动须移除，失败证据保留；不实施条件合批。
- 本轮仅OPT01–04，不实施粗筛、解码复用、候选关联、设备/精度/模型/采样/缩放/画质变更。

## 标准
1. 01原逻辑仅加聚合计时，保持旧pose_inference_s等含义，内部输入准备/模型调用/结果转换单列，嵌套不重复相加。诊断不冒充提速。
2. 02仅同帧0/1/2有效裁剪，最多2，CPU与现有模型配置不变；保持人物身份/顺序/IoU/坐标映射/LK。
3. 03仅C已知帧身份启用最多3帧的单帧预处理张量缓存；组顺序、数值、每组模型调用和片尾行为不变；A/D及现有无帧ID调用不启用缓存。
4. 04仅pose与TrackNet的RGB额外copy；实证独立/连续/数值严格相同再删，必要转换保留。
5. 优先原始回合区间与导出区间一致。真>3秒不新增漏失/减少已保留对打内容；真<=3秒新增损失须逐例人工确认；不新增独立非回合。差异无法解释不得通过。旧标签/缓存不冒充本轮准确率证据。
6. 保持正常产品入口/权重加载校验/balanced导出，完整耗时和资源证据含新增成本；短片每版一次，不推断稳定收益/30分钟验收。
7. 通过必要的有意义的定向检查、pnpm run test:backend、git diff --check及独立功能/代码/文档验收。模拟检查不替代真实推理导出。

## 角色与阶段
- D开发：developer/d/input.md → output.md，只能写其输入允许区域。
- 找球开发：developer/c/input.md → output.md，只能写其输入允许区域。
- 两线可并行；共同文件recognize.py按函数严格分工，禁止整文件覆盖别人变更。
- 每项来源与增量patch保存在各自developer目录，主控用于冻结单项版本。两线交付后暂停写入，主控协调真实模型探针与正式运行，均串行。
- 验收：verifier/input.md → output.md，不读developer通信目录，不修改实现或标准。验收前主控保存完整实现文件SHA/差异摘要及轮次。
- 当前D清理第2轮已交付并停止写入，最终保留源码106项后端测试通过；两线已暂停；真实数值探针、OPT01/02 D 与 OPT03 C 完整单项运行已完成。D 无条件合批有两处边界变化，未通过效果验收；用户已明确本轮暂缓批处理，进入D第2轮移除batch产品代码并保留01/04，当前D最终保留组合正在测量；C单项/组合和A单项输出等价；最终D295.94秒且完全等价，但模型阶段降幅超过copy贡献，追加一次同源码OPT01原版对照以核实跨运行漂移。原版对照339.24秒且输出等价，阶段报告已明确墙钟归因不确定；共7次实际运行全部完成，准备冻结独立验收。无进展轮次0。连续三轮无实质进展按skill保存并停止；不能一次失败就否定方向。

## 输入与证据
- 固定短片：apps/video-clipper/reports/performance-first-round/inputs.json（A/C/D，原基线SHA不变）。
- 准备权重：/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/prepared-models，禁止下载/改写原权重。
- 复用/Users/bytedance/workspace/experiments/smash-suite/.venv（临时ignored链接）；明确从任务目录导入实现。
- 原基线：/Users/bytedance/.codex/worktrees/performance-baseline/smash-suite/apps/video-clipper/.runtime/performance-baseline/baseline。原报告/证据/旧WT保留。
- 新大证据：apps/video-clipper/.runtime/performance-first-round/；小摘要/正式报告：apps/video-clipper/reports/；执行流水：本目录。

## 测量与交付
- 先单项：D仅细计时、D仅批处理、C仅缓存、A仅TrackNet copy；pose copy先真实裁剪独立数值对照。再对实际有效项做D/C组合完整短片检查；异常才补对应原版对照，不默认长片/全组。
- 版本通过增量patch与SHA冻结，绝不把组合数据标成单项。runner真实app.benchmark保持现状。
- 独立验收通过后本地提交任务实现和报告，保留工作目录等待人工确认，不合入/推送、不删旧基线。develop保持进行中。

## 最终交付状态

已完成，待人工确认。独立验收acceptance-1完成106项正常权限后端测试、真实MPS四窗口与无frame_ids核对及完整证据审阅；文档状态经acceptance-closeout-2/3收口，第3轮57份SHA全匹配并最终通过。最终保留OPT01/03/04；OPT02按用户决定本轮暂缓，其调用减少、误删案例与墙钟归因不确定性全部保留。

本地提交由主控授权机械Git角色执行，提交完成事实与准确版本以本任务分支Git HEAD及最终工具核对为准，不把自指向commit哈希反复写回文档。尚未合入develop或推送。develop认领保持进行中，整体性能优化任务5也仍进行中，等待人工确认首轮集成及下一方向，不自动领取后续任务。临时.venv环境链接与.runtime大证据不提交Git；工作目录与原基线保留。

## 报告整理返工轮（2026-10-21）

用户确认将首轮阶段报告正文移入性能优化专题，并要求每项先介绍原理、统一用词，表格明确优化前后的参照与变化。沿用任务分支，基点 ba0fd88b4563c5366a5dcdac8c5a941573a1a65b；本轮只修订文档，产品实现、既有测量证据与旧基线保持冻结。

- 正文目标：`docs/features/performance-optimization/reports/first-round.md`；测量JSON/CSV/图片仍在应用目录，执行记录仍在本目录，不保留旧正文或跳转。同步规则与活动入口。
- 开发交接：`developer/docs/revision-input.md` → `revision-output.md`；不读取验收角色通信目录。
- 原功能与代码验收继续适用于未变实现；本轮另做文档、对照数字、相对链接与差异检查，冻结后独立复验。历史冻结清单不改写。
- 当前阶段：文档开发已停止，主控补齐表后空行、同配置串行运行说明和原版一致性证据后冻结，进入独立文档复验。主目录已有规划改动和ideas/outputs保持原样；不合入、不推送。
