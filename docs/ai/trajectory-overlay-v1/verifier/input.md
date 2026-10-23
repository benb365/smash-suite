# 独立复验 · 轮次3

## 隔离与版本

只在 `/Users/bytedance/.codex/worktrees/trajectory-overlay-v1/smash-suite`，codex/trajectory-overlay-v1，基线94a8465验收。沿用round1-input.md与../task.md批准标准，不新增量化精度门槛、不降低逐拍基本效果。不得读developer通信目录；只写自己的output/临时证据，不改实现或标准。两位开发停止后主控发开始信号。

本轮23代码文件冻结版本：`6f6379e21c04756264a5f7c6153c1581e66146a30c5efa457cb408c4fd3c9f71`，见freeze.json。开始/结束核对实际内容；输出分别判功能、代码、文档，列本轮证据与未执行项。

## 变化和必须核对项

- 删除将缺口后重新出现视作新触球的弱推断，以及根据该推断强行修改后续击球方的分支。直接观测优先于弧线推断。
- 修正候选连锁聚成过长簇、同侧贪心吞掉独立触球、孤立短顶点抖动优先于前后弧线的排序。缺少中间对手接触则明确unknown，不补造交替。
- 末拍落地不能用于中间同侧事件；保留截断/末时间验证及前轮改善。

必须对照 A2 75.2–79秒，确认约76.16远端出球、约78.00近端回球、78.96远端。75.84重新出现不再算新触球，不能为已撤回的76.52–76.72恢复动作补造事件。完整画面包含高空球区域，不仅看裁剪球场或选手挥拍。

A1除原24.64–28.48外，重点看106–109秒网前交换、149–153.84秒尾段：本轮保留149.16 far、150.16 near、151.12 far，150.40孤立抖动已拒绝。独立判断真实方向/来源，而非仅检查数量。

开发检查了两样本全部7回合、保存18张原帧诊断。独立检查这些拼图对应真实源和当前成片，并结合原已选连续片段判断仍否有明显错误。不得仅凭更多触球或unknown通过，也不要求超出首版的全量精确人工真值。未知段不得维持错误旧箭头，整个困难窗口一律隐藏不能代替恢复可确认分拍。

## 当前真实缓存与成片

源视频、TrackNet和YOLO缓存保持原摘要，禁止重跑模型/下载。当前 `modules/trajectory/.runtime/round3-evidence.json` 是算法代码/结果/输入摘要；正式报告 `modules/trajectory/reports/trajectory-overlay-round3.md`。原帧诊断清单 `modules/trajectory/.runtime/round3-event-audit.json` 和各样本 `round3-audit/`。当前A1为42触球/49区间，A2为25/26，unknown不等于触球，类别数从结果实际读取。

结果A1 SHA `b526b4f0e221c55d9bf7cc7a69532fa4d9791135c8102f7afee52e95215b6505`，A2 `8525aeeb5bf57e07d746b34efef43994846e36993a53f908fe40fe7ce981aeb9`。当前analyzer SHA `d4cbb3e8497fd8abaa73f4673905ebb090a617f9cacbb18b09af7a042affe5f9`。

本轮产品真实输出在 `.runtime/trajectory-overlay-v1-product/results/round3-offline-replay/`，含summary、review、a1/a2的MP4/ASS/结果和实际帧；必须用本轮，不能拿旧轮片验收。产品报告已整理为当前结果和历史边界。仍是“真实历史观测离线复算和实际导出”，不称冻结版本完整API/模型单次重跑。

原片统一技能查看器数据 `modules/trajectory/.runtime/review-round3.json`，本轮只读地址 http://127.0.0.1:55849/；可能无浏览器inventory。严格区分网页未执行与实际原帧/成片已检查，不反复启动服务、上传或运行模型。前端/UI/worker/media实现未变，先核对前轮摘要，复用已通过的前端和配置UI结果，必要时以直接真实帧检查实际烧录。不得另造HTML。前两轮证据已存 `.runtime/trajectory-verification/round1/`、round2/。

## 独立检查和停止

算法自检81项、后端127项只是开发结果；请独立运行当前后端、缓存截断复现、当前真实复算/实际成片核对、文档构建、diff check。前轮未变的前端双构建/类型及基础媒体可在哈希吻合后复用，无新疑点不重复。pnpm包装可能先触发自动安装并因约定node_modules符号链接失败，或被release-age策略挡住；直接运行已安装入口，不安装、不改锁/供应链设置。

只对已批准基本效果给结论，不能把预测数量/低残差称准确率；发现真实缺陷仍报告不通过。结束output后停止。实现若再次变化必须重新验收。
