# 路线图专题归位 · 当前轮次输出

- 两份 `docs/plan/roadmap.md` 已删除独立的“二维球路分析与剪辑叠图”章节；主目录任务 15/16 链接改指 feature README，任务 worktree 原有链接保持。其余任务、状态、依赖和并行改动（包括性能优化任务行）保留。
- 新增主目录 `docs/features/trajectory-overlay/README.md`，集中首版二维球路、剪辑叠图范围、研究验证入口和优化文档链接；任务 worktree 专题 README 仅补研究/验证与播放同步边界。两份 `optimization.md` 未修改。
- 检查：两份 roadmap 均不再含该独立章节，15/16 链接目标存在；两目录 `git diff --check` 均通过。性能优化行保留；未运行产品测试、模型、导出或独立复核，未提交或集成。

# 路线图后续方向归位 · 当前轮次输出

- 按纠正从主目录与任务 worktree 的 `docs/plan/roadmap.md` 移除“高远球精度”和“A场景扩展”具体方向；保留15/16蓝色“演进中”、P2、16依赖15，以及A场景首版在本地任务分支、尚未集成的认领信息。节点只写“二维球路分析／演进中”。
- 两仓库新建同内容 `docs/features/trajectory-overlay/optimization.md`，分别记录高远球准确性和场景扩展当前问题/目标，并注明算法、场景顺序和验收待确认。worktree专题 README 只增加优化文档入口；主目录未创建专题 README。
- 编辑前查看了两目录状态并保留其他并行修改。两目录 `git diff --check` 通过；确认优化文档存在、两份内容一致，roadmap 与专题 README 链接均指向新文件。未运行产品测试。

# 路线图状态标记更新 · 当前轮次输出

- 仅定点更新主目录与任务 worktree 的 `docs/plan/roadmap.md`：任务 15/16 总览与依赖图统一标为蓝色“演进中”；16 移除名称斜体，保持 P2 和直接依赖 15。
- 两份认领都保留本地 `codex/trajectory-overlay-v1` 任务分支及未集成说明：“A 场景首版在任务分支；高远球精度和场景扩展待完善”。任务说明中的实现范围和其他任务规划未改。
- 在两份球路专题段落补“后续演进”两项：改善高远球估计准确性；从 A（比赛高视角）扩展至其他拍摄场景。主目录原研究计划只增一句首版位于任务分支、尚未集成。
- 编辑前分别记录了主目录与任务 worktree 状态；保留已有其他会话修改。两目录 `git diff --check` 均通过；主目录路线图还含其他会话的既有差异，本轮只改本任务节点、认领及专题段落。未运行产品测试。

# 人物位置推算起点 · 当前轮次输出

## 实现与验证

- `modules/trajectory/constraints.py` 接受可选 `player_tracks`：同侧人物精确时刻优先，无记录时仅用击球前后 220 ms 内的同侧位置插值，不外推。违规起点采用人物位置并保留原坐标、来源、估算方法/时间与拒绝原因；估算仍不合规则隐藏。终点按有效的下一击球起点、再到下一击球者人物位置顺序替换。原未解析不恢复，末拍坐标保持不变。
- analyzer 在输出前传入当前人物轨迹并统计起点估算数/合规修正数；产品 `write_overlay` 对保存后的 paths 继续调用共享约束函数。更新了 trajectory README、video-clipper requirements、trajectory-overlay 专题 README 和产品报告。
- 测试：`.venv/bin/python -m pytest modules/trajectory/tests apps/video-clipper/backend/tests/test_product.py -q -p no:cacheprovider`，48 passed，1 条 Starlette/httpx 弃用提示。`git diff --check` 通过。
- 重用 round3 原始逐拍、回合、真实人物轨迹及球点缓存，通过现有 `write_overlay`、`selected_ranges` 和 `render` 生成新结果；没有模型调用、完整分析、服务、独立复核或视觉审查。

| 样本 | 时间段 / 触球事件 | 起点估算 / 合规修正 | 终点替换 / 隐藏 | 约束后分段（预测 / 下一拍 / 检测落地 / 未解析） | 时长 / MP4 SHA256 |
| --- | --- | --- | --- | --- | --- |
| A1 | 49 / 42 | 1 / 0 | 6 / 3 | 16 / 16 / 3 / 14 | 46,420 ms / `e6c5e71a7ee777c31b681538bb2d02eb7367eb9f6263aefc04017f362b8b31c4` |
| A2 | 26 / 25 | 1 / 0 | 6 / 2 | 4 / 17 / 1 / 4 | 25,980 ms / `784a863ac0bf6362b17057c8bc42b64e27b01a2f63182958acba6d2cddff825f` |

两次人物起点估算仍越过近端底线（A1 y=13.5178 m、A2 y=13.5797 m，场界为 13.4 m），所以箭头按规则隐藏；估算 2 次，合规修正 0 次。ASS 与 MP4 哈希均与上一轮场内限制导出一致，因为这两条估算仍对应隐藏箭头。新 JSON、ASS、MP4、round3 输入副本、人物轨迹副本和完整指纹见 `.runtime/trajectory-overlay-v1-product/results/player-origin-constraints/summary.json` 及 `a1/`、`a2/`。当前交用户人工查看，不启动独立复核。

## 上一轮记录

# 产品开发 · 轮次1输出

版本：`codex/trajectory-overlay-v1`，基线 `94a8465`。

## 修改

- 前端高视角上传配置增加默认开启的“在成片中显示球路”，可关闭；切换到其他视角时开关关闭且不显示。选择随页面会话保存。
- `ProcessRequest` 增加 `show_shot_paths`；worker 仅在高视角开启时创建 `ObservationLog`、将其传给 `recognize`，再调用 `analyze` 并保存观测、meta 和 `shot-paths.json`。分析计入既有识别阶段。关闭时删除该会话中上一轮可能生成的轨迹文件，并走原渲染参数路径。
- 新增 `app/trajectory_overlay.py`，生成固定右上角 ASS 小球场及每拍统一颜色直线箭头。按 `export_ranges` 对事件作半开区间裁切，并把源时间映射到连续成片时间。未解析拍不生成箭头。
- `modules.media.video.render` 只增加可选关键字 `overlay_ass`，在现有剪辑及 setpts 后烧录，不依赖轨迹或产品模块。
- 更新 video-clipper README/requirements 和 media README。产品实现与验证记录见 `apps/video-clipper/reports/trajectory-overlay-v1-product.md`。

## 验证

- 完整后端套件 `.venv/bin/python -m pytest`：使用授权权限运行，111 项通过。
- 产品媒体测试：14 项通过；worker 模拟球路路径与关闭路径的阶段测试通过。
- 修正短发球线后，实际 ASS 烧录测试和 worker 球路调用测试通过（2 项）。
- 前端 TypeScript：`apps/video-clipper/frontend/node_modules/.bin/tsc --noEmit -p apps/video-clipper/frontend/tsconfig.json` 通过。
- 前端构建：直接运行已安装的 Rspeedy、Rsbuild 两步构建，通过。
- `git diff --check` 通过。
- `pnpm run typecheck:frontend` 被全局 pnpm 的 release-age 检查挡住，注册表缺少 `watchpack@2.6.3` manifest；本地 TypeScript 等价命令通过。主控在同一 worktree 使用已安装 VitePress 构建成功、退出码 0；先前记录的 154 条断链未复现。

## 真实 API 联调诊断

首份真实产品 API 样本 `m1-short-a1-01-20261015` 已完成：SHA256 `e2ea56c398507cc0c1679088121f26ac5a0d6b23ad12502151fb855b13966ef2`；追球记录 4,200 帧、人物检测 1,400 帧，得到 37 拍（预测落点 13、下一拍位置 19、检测落地 1、未解析 4）和 5 个回合；识别耗时 31.58 秒，输出 46.44 秒 MP4。抽检实际 MP4 的 1.06 秒帧，右上角场地与黄色箭头均已烧录。产物保存在 worktree `.runtime/trajectory-overlay-v1-product/results/m1-short-a1-01-20261015/`。

算法侧在该 worker 开始后更新了 `modules/trajectory/analyzer.py`，所以该产物仅是 API 联调诊断，不能当作冻结版本验收。首份 raw API 响应未能保存。首份 worker request、结果、日志、球点缓存、逐拍 JSON、ASS 和 MP4 已保留。

## 冻结观测离线复算与导出

按冻结算法版本复用历史完整追球观测和最终 `shot-paths.json`，通过当前产品 `write_overlay`、媒体 `selected_ranges` / `render` 生成 A1、A2 实际最终 MP4。该证据是“真实历史观测离线复算与成片导出”，没有重跑 TrackNet/YOLO，也不是最终代码一次完整 API/模型端到端重跑。算法 SHA256 为 `c1b8c8bfdf3d01c803708c098654fdb7a3cb380d4ae7b97e07232b2ce0d1bb71`，court SHA256 为 `42dc1583a5f1171c320da0c95c38ddf2b9fb2eb7f9a42d4a6a209e0f1f7d4b48`。

| 样本 | 源 SHA256 / 完整观测帧 | 最终逐拍文件 SHA256 | 拍数 / 箭头 | 成片时长 / SHA256 | 无箭头帧场地区域黄色像素 |
| --- | --- | --- | --- | --- | ---: |
| A1 | `e2ea56c398507cc0c1679088121f26ac5a0d6b23ad12502151fb855b13966ef2` / 4,200 | `b62d5c193a32bc8b26ab470c8c4e82766070a0abb0a86e3be73b8ae02dade4a9` | 35 / 34 | 46,420 ms / `02b579758686a0322771f9e4c3e2f10d8e71078074ed9fd736e746c27427a21d` | 0 |
| A2 | `0ae60f5564e9fed6058c87cdc573b5a07d5e4d8ef6137245b67f59ede5d0edc9` / 2,421 | `d0a960b5d64c8ab9675219a272678174f3b98358dd217a4a97a9af0551525046` | 23 / 22 | 25,980 ms / `088f64cf2a9a12b96273e56babce180f87b8af92c3058dd610c3eb8d4d93577f` | 0 |

两份输出均为实际导出的 MP4；导出区间、ASS、输入输出指纹、抽帧和检查结果见 `.runtime/trajectory-overlay-v1-product/results/frozen-offline-replay/`（索引 `summary.json`、`review.json`，逐样本目录含 `output.mp4`、`frame-arrow.png` 与 `frame-no-arrow.png`）。主控已查看 summary 和两份带箭头抽帧；独立视觉验收由验收角色继续完成。本角色不追加播放或检查。

## 轮次2文档更新

按主控要求更新了 `apps/video-clipper/README.md` 的球路进展；算法随后收到新冻结信号，round2 导出结果见下节。

## 轮次2冻结结果离线导出

复用两样本历史真实球点观测和冻结逐拍文件，经当前产品叠图与媒体选择/导出函数生成新 MP4。模型调用数为 0；此项是历史观测离线复算与成片导出，不是完整 API/模型端到端验收。当前 analyzer SHA256：`93b287ee903082e575b992253c9f6205fbafbb13d922aac30bef54923f245e22`。

| 样本 | 源 SHA256 | 观测帧 | 时间段 / 触球事件 | predicted / next_hit / detected / unresolved | 目标窗口（源 → 成片） | 成片时长 / 输出 SHA256 |
| --- | --- | ---: | ---: | --- | --- | --- |
| A1 | `e2ea56c398507cc0c1679088121f26ac5a0d6b23ad12502151fb855b13966ef2` | 4,200 | 41 / 37 | 15 / 17 / 3 / 6 | 24,640–28,480 → 7,620–11,460 ms | 46,420 ms / `c066ecb2cd83b94dc365303f3e87b17ba482419f8ca8814b75fbc021421e4033` |
| A2 | `0ae60f5564e9fed6058c87cdc573b5a07d5e4d8ef6137245b67f59ede5d0edc9` | 2,421 | 27 / 25 | 11 / 12 / 1 / 3 | 73,920–76,120 → 9,660–11,860 ms | 25,980 ms / `8b326bf0a8a330c53d588f720d86c26a155031cb295363f76d58e2e8e7c09da8` |

41 / 27 是包含未知区间的时间段数；实际触球事件为 37 / 25。证据与统一查看器数据位于 `.runtime/trajectory-overlay-v1-product/results/round2-offline-replay/`：包含两份 MP4、ASS、当前逐拍及回合结果副本、输入/观测/源码/输出指纹、区间、`summary.json`、`review.json` 和真实抽帧。目标窗口内抽帧时间为 A1 成片 8,700 ms（黄色像素 581）、A2 成片 9,900 ms（919）；无箭头抽帧均为成片 180 ms（0）。这些像素数据仅作烧录定位证据，不代替目标窗口的逐拍人工复核。结果交独立验收，未宣称通过。

## 轮次3冻结结果离线导出

复用了 round3 evidence、当前两个 shot-paths、原始回合和历史真实观测，用产品叠图及媒体选择/渲染函数生成新成片。模型调用数为 0；未启动服务或浏览器。分析器 SHA256 为 `d4cbb3e8497fd8abaa73f4673905ebb090a617f9cacbb18b09af7a042affe5f9`；其余源码、输入和观测指纹保存在本轮 summary。

| 样本 | 触球事件 / 时间段 | 预测 / 下一拍 / 检测落地 / 未解析 | 事件来源方法计数 | 目标窗口（原片 → 成片） | 成片时长 / 输出 SHA256 |
| --- | --- | --- | --- | --- | --- |
| A1 | 42 / 49 | 24 / 11 / 3 / 11 | observed_velocity_turn 41；occluded_contact_arc_intersection 1 | 106–109 s → 30,740–33,740 ms | 46,420 ms / `9a222596a4ed8d1aae5440f3a43aaeb411f952302ef6c6f504405f178d300a94` |
| A2 | 25 / 26 | 11 / 12 / 1 / 2 | first_observed_flight_near_player 1；observed_velocity_turn 22；contact_after_observation_stall 1；observed_contact_between_occluded_arcs 1 | 75.2–79 s → 10,940–14,740 ms | 25,980 ms / `22128582a9ebd173ccdc196ed199e2ca427f4a5912bc1aabb544fe50786e607d` |

“时间段”包括未解析区间，不应当作触球事件数；来源方法数量是 round3 event audit 里的触球事件方法计数。目标窗口带箭头抽帧分别为 A1 成片 31,420 ms（黄色像素 671）和 A2 成片 11,740 ms（422）；无箭头抽帧均为成片 180 ms（0）。完整 MP4、ASS、区间和 viewer 数据位于 `.runtime/trajectory-overlay-v1-product/results/round3-offline-replay/`，其中 `summary.json` 保存源、观测、逐拍、源码和输出完整指纹，`review.json` 保留逐段时间轴及目标窗口。像素计数不能替代分拍人工验收；当前输出交独立复核，未宣称通过。

本轮导出文件和 summary 已在脚本最后一条控制台摘要字段名不匹配前写出；脚本退出码 1 仅来自该摘要打印错误，不影响已保存的成片和证据文件。

## 场内与跨网限制

- 新增 `modules/trajectory/constraints.py` 的共享 `constrain_shots`：分析结果保存前和产品 ASS 生成时共用；只处理每回合非末次真实击球，跳过无起点的未知段，末次真实击球豁免。违规时尝试下一次真实击球起点，失败则隐藏并标记 unresolved；诊断保留原终点、类型和拒绝原因。
- 修改 analyzer、模块导出和产品叠图入口。新增约束单元测试与多回合 ASS 测试。
- 更新 trajectory 模块 README、video-clipper requirements、trajectory-overlay 专题 README 与产品报告。未修改模型、算法识别或物理拟合逻辑；没有启动独立复核，当前交用户人工查看。
- 验证命令 `.venv/bin/python -m pytest modules/trajectory/tests apps/video-clipper/backend/tests/test_product.py -q -p no:cacheprovider`：41 passed，1 条 Starlette/httpx 弃用提示；`git diff --check` 通过。导出复用 round3-offline-replay 的真实 source、观测、rallies 和 shot-paths，未调用模型；两份旧 MP4 原样保留。

| 样本 | 触球事件 / 时间段 | 替换 / 隐藏 | 约束后分段（预测 / 下一拍 / 检测落地 / 未解析） | 时长 | SHA256 |
| --- | --- | --- | --- | --- | --- |
| A1 | 42 / 49 | 6 / 3 | 16 / 16 / 3 / 14 | 46,420 ms | `e6c5e71a7ee777c31b681538bb2d02eb7367eb9f6263aefc04017f362b8b31c4` |
| A2 | 25 / 26 | 6 / 2 | 4 / 17 / 1 / 4 | 25,980 ms | `784a863ac0bf6362b17057c8bc42b64e27b01a2f63182958acba6d2cddff825f` |

完整每例源/观测/round3/约束后 JSON/ASS/导出和代码指纹见 `.runtime/trajectory-overlay-v1-product/results/court-constraints/summary.json` 与各自 `a1/`、`a2/`。下一步只需用户人工查看，不做自动复核或继续调参。
