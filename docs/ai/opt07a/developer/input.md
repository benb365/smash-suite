# 第1轮开发输入

实现版本：develop 94a8465946f97610d91c2bb75b6b9930a93650e5 + 当前任务worktree已迁入的 predictor.py、test_preprocessed_cache.py、probe.py 草稿。以task.md为授权和标准。

你是本轮开发方。只在任务worktree工作，禁止读取 verifier/；不改 task.md 或验收标准，不运行真实模型/耗时（由主控串行执行）。允许读 task.md、根与模块 README、原目录已批准需求；允许修改 predictor.py、对应tests、docs/ai/opt07a/probe.py、recognition.py、developer/output.md，以及负责本变更的模块README。不要全仓格式化。

1. 检查迁入的两行预处理与测试，简化过长注释，但不得添加兼容分支/公开开关/封装。当前输入为解码BGR三通道uint8。补核对已有调用中的合法其他dtype行为，不得凭空扩大支持范围。
2. 检查probe.py草稿：baseline从冻结源码动态导入，inplace只替换.float()/255，candidate当前生产。不同动态模块的ShuttlePoint需asdict/astuple后逐字段严格比较，不得用容忍误差。完整读取A/C/D只保存各9帧+首7C帧；actual batch/heatmap输出严格比较，记录frame_ids/PTS/cache；无任何模型下载。检查ROOT/sys.path必须让modules从当前任务worktree导入（复用主目录.venv为同版本依赖，仅运行时，不得从主目录导入生产modules）。探针输出目录应使用显式路径。
3. 新建精简 recognition.py：参数 --variant baseline/candidate --case A-short/C-short --inputs --models --reference-source --output。先校验videoSHA/ASSETS权重SHA、确认MPS可用，否则失败；baseline在import recognize前替换package TrackNetPredictor为冻结类。每次新进程，直接当前recognize，不用历史patch/HTTP/导出。torch4/OpenCV1，Statistics(enabled=True)+mps_sampling。保存完整predictions/details、selected_ranges(padding_ms=500)推导范围、statistics、进程RSS/CPU每秒采样及元数据（版本、代码hash、环境、来源SHA、MPS；识别计时包含模型初始化，校验/加载输入清单在计时外）。禁止静默降CPU或覆盖输出。确保源码来源是任务worktree。
4. 只运行聚焦回归与脚本语法检查，不与主控模型运行并发。交付output写明第1轮、实际源码hash、修改文件和已执行/未执行验证。完成后暂停所有开发，等主控冻结与独立验收。

## 主控补充检查点（同第1轮）

当前probe草稿load_source_class创建types.ModuleType后没有注册sys.modules；dataclass可能在动态类构建时失败。请以不构造模型的方式实际调用build_variants，修正并验证动态加载。ROOT/sys.path应在首次import modules前设置，记录并断言modules来源。probe缺少对ASSETS球模型SHA的实际比较与MPS可用检查，也请补齐；当前只记hash不足以证明加载正确权重。inputs默认应首轮inputs，而非旧baseline清单。不要额外创建兼容分支或放宽数值比较。

## 第1轮主控小样实测反馈：选保留版本

开发尚未进入独立验收，现按已授权的“先小样对照，选保留版本再A/C测速”调整候选。三版真实A/C/D模型IO严格等价的原始证据在 apps/video-clipper/.runtime/opt07a/probe-controller/。主控随后用同一A短片真实首帧、torch4/OpenCV1、18轮交错顺序测了包含resize的CPU预处理；preprocess-small.json显示原版中位1.775ms、仅原地1.670ms、合并转换5.426ms。后者比原版约3.06倍，少RGB数组不值得此已观察额外CPU工作。torch profiler确认原版aten::div分配24883200字节、原地div_为0；这不是进程峰值结论。

请仅保留 `.float().div_(255)`，恢复 cv2.cvtColor 与RGB uint8路径；不要保留产品切换或fused兼容分支。测试继续严格比较旧公式并查输入未变。修改probe为明确生成 baseline/inplace/fused 三种实验类，current生产类可与inplace公式相同，不能再断言当前必为第三种不同公式；须保证实验三公式互异，比较三实验与当前真实batch/热图/points/candidates均严格一致。现有probe-controller的失败候选证据保留，不覆盖；下一次输出probe-retained，当前实际代码再次复核。recognition.py接口保持baseline/candidate即可，candidate加载现在原地版。README/输出说明fused已因小样CPU成本不采用。只运行聚焦测试和无模型build_variants自检；交付后暂停，主控继续串行真实模型。更新developer/output.md本轮实现hash，保留此前交付与实测反馈由本input记录，不读verifier目录。

## 第1轮收尾补充（仅文档状态）

独立功能、代码、文档检查已通过，生产实现不再改动。主控已找到本机 pnpm 正式运行选项 `PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false`，仅对本次后端测试跳过不相关 JS 自动安装；不改变供应链安装策略。最终测试结果由主控和验收方记录。

请只把专题 README 中 OPT-07A 的“正在独立任务分支验证”改为“已在任务分支完成，待人工确认”，保持其余结论和链接；不要改生产代码、测试、应用报告或其他文件。更新自己的 output 补记这次纯状态修正后暂停，主控将重新冻结该文档并请验收方复查。
