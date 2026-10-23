# OPT20 第1轮独立验收

## 结论

功能、代码与文档核对通过。独立后端检查和 D-short 完整产品 API 重跑均成功；新候选与冻结基线的产品结果、全部 person-signals、决策 trace、模型工作量和成片媒体结构一致。结论仅适用于本次约 250.9 秒 D-short 等价对照，不构成准确率、30 分钟素材或稳定性能收益验收。

## 冻结与代码

- HEAD 为 `5bb39fa69181e86c21bde20e74d951f1cb2ca415`；验收前后都与冻结基线一致。
- 冻结文件及运行证据共 46 项，验收结束时 SHA256 全部匹配；实现文件、正式报告和任务标准的冻结 SHA 也匹配。未改实现、报告、标准或冻结文件。
- 静态完整差异符合约定：`recognize.observe` 移除 personal 场景的 body_features import、全画面灰度缩放、Farneback、previous gray/time 状态及 body_motion 赋值；保留 appearance 描述子。`players_v2.follow` 只移除 body_motion 的透传，匹配与 cost 不变。`trials.series` 只移除 upper/articulation 数据及返回键，times/speed/present/ball 和 median speed 保留。删除的 body_features.py 已无活跃 caller；RallyInterval 仍有其它调用者。
- Pose 裁剪推理仍按原人物观测执行。肩腕 PyrLK 正反向计算、基于真实 PTS 的 dt、+1/+3/+5 帧调度与场景规则未改。生产源码中已无 Farneback 调用；保留 PyrLK 调用。
- `modules/rally/README.md` 没有承诺 D 使用全画面光流，无需同步改动稳定行为文档。正式专项报告如实保留本次范围和验收限制。

## 独立重测与结果

1. 后端检查：`PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false pnpm run test:backend`，结果 `107 passed`，12.59 秒，1 条 Starlette/httpx 弃用警告。
2. 真实候选：按 `verifier/input.md` 指定命令调用 `app.benchmark`，输入为冻结 D-short（视频 SHA256 `360e3de1018a9656770ea432c903afba44cff29c0052f03ea65606a5200867fd`），复用指定本地模型权重。状态 completed；结果 status passed。独立证据位于 `apps/video-clipper/.runtime/opt20-flow/independent/D-short/`，报告在 `independent-report.json`。
3. 产品计时：准备 0.530 秒，识别 260.998 秒，成片 12.733 秒，总计 274.261 秒。该单次计时只记录本次观测，不据此推断稳定收益。报告含一条 WebSocket lease `1001 going away` 关闭诊断，但 benchmark/产品结果完成，所有要求的证据均生成。
4. 运行 `docs/ai/performance-first-round/controller/validate.py` 对比独立候选和 primary 冻结基线，写入 `apps/video-clipper/.runtime/opt20-flow/independent-equivalence.json`；返回 `passed_equivalence=true`。raw predictions、export ranges、输出时长、质量、padding、warnings 六项均相等。
5. NPZ 键集合严格相等，包含 13 个键：times、arm、high、ready、pickup、speed、present、ball、lkarm、lkhigh、lk_valid、foot_speed、foot_valid。逐数组以 `equal_nan=True` 比较，形状及值全相同。`decisions.json` 字节相同，选中 track IDs 两边均为 `[58, 40]`。
6. 工作量计数逐项相同：TrackNet 2509 次/7527 输入帧，人物检测 314 次/1255 张图/3373 个框，7527 帧两遍解码（15054 帧），7527 native observations、1 shifted observation、5018 Pose 转换帧、2432 次 Pose 调用和 2432 crops。球、YOLO、Pose 权重 SHA 与冻结报告相同。
7. 比较器完整解码候选与基线 MP4 的视频和音频到 EOF，结构、帧数和 PTS 序列相同：视频各 4413 帧，音频各 6336 帧，PTS 严格递增。输出成片 SHA 也相同。

## 文档结论与未覆盖项

正式报告 `apps/video-clipper/reports/opt20-flow/README.md` 与 `summary.json` 已说明结果仅支持该 D-short 样片等价；未匹配人工标注、不作准确率结论，未覆盖 30 分钟素材，单次计时不是稳定收益承诺。验收期间它们的冻结 SHA 未改变。

最终执行 `git diff --check` 通过。未验证跨素材效果、准确率及 30 分钟验收；没有新增测试，因为本项是经真实产品 API 与完整候选/基线结果对照验证的纯死数据删除。
