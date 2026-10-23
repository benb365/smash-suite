# 第1轮独立验收输入

唯一目录 /Users/bytedance/.codex/worktrees/opt07a-tracknet/smash-suite，分支codex/opt07a-tracknet。只读 task.md、acceptance-freeze.json、本input、实现/需求/报告；禁止读取 developer/ 通信目录，也不要从旧聊天中的“通过”字样推断结论。所有命令显式workdir。开发已暂停，本轮冻结后不得改实现/标准。你只写 verifier/output.md 及临时验证结果；报告必须写第1轮、实际版本SHA是否匹配冻结，功能/代码/文档各给结论。

## 授权与需要独立检查的事项

根AGENTS与仓库run-task-workflow为准，task.md列完整标准。原版source须与 `git show 94a8465946f97610d91c2bb75b6b9930a93650e5:modules/models/tracknet/predictor.py` 字节一致。最终生产仅一处 `/255` -> `.div_(255)`；合并颜色/类型转换已因小样慢弃用，不应有产品开关或NumPy融合分支。检查原图所有权、缓存、布局/尺寸/精度/缩放/热图及返回契约均保持。

1. 核对冻结文件SHA、实际diff，以及正式报告里的数值/范围。A/C识别四份原始run/result/statistics/resources在 `.runtime/opt07a/recognition/`；检查状态completed、版本/配置/媒体/权重一致、计数/原始区间/推导导出范围精确一致。单次墙钟不能声称稳定提速，C预处理略增必须如实写；RSS是本进程1秒采样不是产品总进程峰值；MPS不加RSS。OpenCV5.0.0请求setNumThreads(1)后的初始记录实际18，不能按“固定1线程”判实验。当前生产调用未改，两版环境相同。
2. 独立重跑最终关键真实检查：按 docs/ai/opt07a/README.md 的probe命令，相同显式inputs/models/reference-source，输出改为 `apps/video-clipper/.runtime/opt07a/probe-independent`（必须新目录）。MPS工具调用需要限制外运行，不能CPU替代；完整解码A/C/D，核对真实batch/热图/points字段/candidates逐值相同和缓存/输入未变。核查生成脚本实际执行路径、断言和保存的张量，不只信JSON布尔。可以独立加载主控model-io.pt核对张量（weights_only=True）及本次新结果；不要读取/运行开发方通信目录。
3. 执行 `pnpm run test:backend` 和 `git diff --check`，记录原始通过数/任何失败、来源、是否本次引入。前端无改不需要跑前端检查。不得因时间临近跳过必需项。
4. 独立检查本轮文档/所属入口，原目录的未提交规划不能当本分支实现。报告应用内数据链接、模型README指向本报告、专题最小状态描述、任务流水不混人类入口；检查严格比较范围是采样31图12组而非17127帧全部热图。没有正式人工真值标签，不得说准确率通过。主控已按统一skill检查实际播放器播放/定位/切换，保存viewer.png；可核对保存review JSON来自result、PTS偏移及截图，不必在你的模型运行时播放视频争用资源。

## 事实边界与交付

本项不导出、不跑D全姿态/长片、不测试前端；没有稳定速度/精确峰值或准确率承诺。对测量证据有具体疑点时先指出根因并仅重跑对应必要对照，不重复全组。真实模型/测速不与其他CPU/GPU负载并发。主控当前没有活跃模型或性能测试，只有暂停播放的统一查看器服务。

完成后写 verifier/output.md 并暂停。若需修改实现或报告，明确阻塞和最小修订要求，不自行编辑；主控会安排返工与复验。只有本轮版本功能、代码、文档都通过才可判独立验收通过。验收后的本地任务提交与集成由主控处理，你不要暂存/提交/推送。

## 第1轮收尾复查

主控已确认你的初次功能/代码/文档结论，原来13项计数现已修正为12。开发随后仅把专题 README 的 OPT-07A 状态从“正在独立任务分支验证”改为“已在任务分支完成，待人工确认”；没有其他冻结文件变化，生产/测试/模型证据均未改变。原冻结清单保存在 acceptance-freeze-initial.json，当前 acceptance-freeze.json 只更新该文档SHA，开发再次暂停。

本机 pnpm12 默认运行前自动 install 引发不相关 JS 依赖 registry 校验；本机 binary 与 config get/list 证实正式 PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN 键。主控实际运行 `PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false pnpm run test:backend`，脚本直接执行 `.venv/bin/python -m pytest`，107 passed、1 条既有 Starlette/httpx 弃用提示，12.66秒。仅本次跳过运行前自动安装；不安装新依赖、不关闭安装时安全策略、不改全局/项目配置。

请独立执行上述 pnpm 命令（权限外运行，避免已知psutil沙箱失败），及 git diff --check；核对当前12文件SHA与初始冻结唯一差异、专题状态措辞。若通过，在自己的 output.md 第1轮报告末尾补记复查结果，并将旧“仍被包装入口阻塞”结论更新为已解决，保留最初失败事实；功能/代码/文档各给最终结论。无需重复已通过且完全没变的真实模型或A/C四次识别。禁止读 developer/目录，不修改实现/标准，不提交；完成后暂停。
