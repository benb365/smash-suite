# Windows 环境与启动

在 Windows 上从源码运行自动剪辑应用，使用 Chrome 或 Edge 操作本机服务。本说明适用于 Python 3.11、Node.js 20.19+；命令在仓库根目录的 PowerShell 中执行。

`codex/windows-latest` 已整合 develop `1080146` 的高级配置、球路叠图及性能改动，完成本轮 A/C/D 三短片的 Windows 真实产品运行。独立效果与长视频验收仍待完成；本轮结果及范围见[整合验证记录](reports/windows-latest-20261023.md)。

## 安装环境

创建独立虚拟环境。已有旧环境发生 NumPy、OpenCV 或 PyTorch DLL 错误时，可改用 `.venv-clip` 作为目录名，保留旧环境。

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

具有 NVIDIA 显卡的机器，先安装本项目固定版本的 CUDA 12.6 wheels：

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu126
```

只使用 CPU 时，将上一条命令的索引地址改为 `https://download.pytorch.org/whl/cpu`。版本配对与索引来自 [PyTorch 官方历史版本说明](https://pytorch.org/get-started/previous-versions/#v280)；显卡驱动需支持所选 CUDA 运行时。

随后安装项目依赖和前端依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -c apps/video-clipper/constraints-windows.txt
npx --yes pnpm@9.15.9 install --frozen-lockfile
```

上述命令使用显式解释器，不需要激活环境或更改 PowerShell 执行策略。若虚拟环境目录为 `.venv-clip`，对应替换安装命令中的 `.venv`。

Windows 约束文件固定了共同验证过的 NumPy / OpenCV 二进制依赖组合；其余共同依赖仍由根目录 `pyproject.toml` 管理。

## 检查模型运行环境

仓库的 `scripts/python.mjs` 在 Windows 使用 `Scripts/python.exe`，在 macOS / Linux 使用 `bin/python`，依次查找 `.venv-clip`、`.venv`，并配置 UTF-8 与应用模块路径。也可以设置 `$env:SMASH_SUITE_PYTHON` 为另一个 Python 可执行文件的路径；显式路径无效时直接报错。

两个环境同时存在时，可明确选择刚安装的环境：

```powershell
$env:SMASH_SUITE_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
```

```powershell
node scripts/python.mjs -m pip check
node scripts/python.mjs -c "import torch, torchvision; print(torch.__version__, torchvision.__version__); print('CUDA:', torch.cuda.is_available(), torch.version.cuda)"
```

NVIDIA 环境还应验证 CUDA 算子确实可执行：

```powershell
node scripts/python.mjs -c "import torch; from torchvision.ops import nms; x=torch.ones((2,2),device='cuda'); print(x@x); print(nms(torch.tensor([[0.,0.,1.,1.]],device='cuda'),torch.tensor([1.],device='cuda'),0.5))"
```

TrackNet 和 YOLO 沿用现有设备选择规则。个人斜侧方场景的姿态估计默认在 CUDA 可用时使用 CUDA，否则使用 CPU；独立调用 `PoseEstimator()` 仍默认使用 CPU。姿态推理默认批大小为 `1`。批大小 `2` 在已检查的 8 张真实人物裁剪对照中出现约 64 像素的关节坐标偏移，目前仍作为实验选项，需另行核对回合区间和成片。

需要固定使用 CPU 时，在启动后端的 PowerShell 窗口中设置以下变量，再启动或重启服务：

```powershell
$env:SMASH_SUITE_POSE_DEVICE = 'cpu'
$env:SMASH_SUITE_POSE_BATCH_SIZE = '1'
```

恢复自动选择设备和默认批大小时，移除覆盖值后重启服务：

```powershell
Remove-Item Env:SMASH_SUITE_POSE_DEVICE -ErrorAction SilentlyContinue
Remove-Item Env:SMASH_SUITE_POSE_BATCH_SIZE -ErrorAction SilentlyContinue
```

CUDA 可用不代表整个任务都在 GPU 上执行；视频解码、部分动作计算和 `libx264` 编码仍包含 CPU 工作。

模型首次使用时按[模型模块](../../modules/models/README.md#环境与文件)规定的固定来源下载并校验。应用默认将模型缓存写入 `%LOCALAPPDATA%\SmashSuite\models`；模块独立运行使用各自的 `weights/`。这些权重不随源码提交。

## 构建与启动

```powershell
npx --yes pnpm@9.15.9 run dev:frontend
npx --yes pnpm@9.15.9 run dev:backend
```

默认打开 `http://127.0.0.1:18780/`。需要避免自动打开浏览器或端口冲突时：

```powershell
npx --yes pnpm@9.15.9 run dev:backend --no-browser --port 0
```

终端打印实际地址。前端修改后重新构建并刷新；后端修改后重启。若希望把模型与临时工作目录放在仓库中，可在启动前设置：

```powershell
$env:SMASH_SUITE_DATA_DIR = Join-Path (Get-Location) '.runtime\clip-app'
```

使用“保存 MP4”选择成片位置。会话临时文件的清理规则沿用[应用说明](README.md#使用)。关闭服务会清理当前临时会话，模型缓存保留。

当前产品支持四项高级配置；未展开面板或请求省略配置时，同样使用[场景默认值](requirements.md#高级选项)。高视角默认四项开启，并默认生成球路叠图；场边和个人视角默认开启帧率上限、缩小找球图像和灰度，关闭动态粗筛。产品配置改变识别输入，历史 CPU/CUDA 对照的区间一致不代表这些新默认值与旧版结果相同。

## 单样本性能对照

`scripts/benchmark_clipper.py` 直接处理一段本地录像，使用已缓存模型生成完整 MP4，并保存阶段耗时、有效配置、聚合统计、设备与核心源码摘要、CUDA 显存峰值、事件和参考区间差异。脚本不下载录像或模型；个人视角的缓存目录须已有校验通过的 `ball_track.pt`、`yolo11n.pt` 和 `pose_kpRCNN.pth`。

该入口用于同一识别配置下的模块对照。`--optimizations off`（默认）显式关闭四项高级配置；`--optimizations default` 使用当前产品的场景默认值。两种模式都不运行高视角球路叠图，不能代替真实产品 HTTP 流程的验收。

将下面四个占位路径替换为本机路径，源录像须为绝对路径。两次运行使用同一录像和模型缓存，各自选择一个尚无基准产物的新输出目录。每次只运行一条命令，等待结束后再运行下一条：

```powershell
$sourceVideo = 'C:\path\to\input.mp4'
$modelCache = 'C:\path\to\cached-models'
$cpuOutput = 'C:\path\to\new-cpu-b1-output'
$cudaOutput = 'C:\path\to\new-cuda-b1-output'

node scripts/python.mjs scripts/benchmark_clipper.py --source $sourceVideo --scene personal --models $modelCache --output $cpuOutput --pose-device cpu --pose-batch-size 1 --optimizations off
node scripts/python.mjs scripts/benchmark_clipper.py --source $sourceVideo --scene personal --models $modelCache --output $cudaOutput --reference (Join-Path $cpuOutput 'result.json') --pose-device cuda --pose-batch-size 1 --optimizations off
```

每个目录包含 `output.mp4`、`result.json`、`performance.json` 和 `events.jsonl`。固定使用均衡质量和前后各 0.5 秒补时；报告区分处理耗时与额外的完整解码校验耗时。`performance.json` 的 `status: passed` 表示执行与导出检查通过；区间回归需查看 `reference_comparison` 的身份核验、区间差异及 `same_order_exact`，不能仅凭该状态认定结果一致。参考文件保持原样，预测区间按原顺序逐项比较；出现区间变化时需结合原片判断影响。音轨完整解码和非空检查不等于音画同步验收。

产品新默认值和球路联用使用 `apps/video-clipper/backend/app/benchmark.py` 的真实 HTTP 入口另行验证。输入例显式设置 `show_shot_paths=true` 才覆盖高视角球路；单独运行上述模块脚本没有覆盖上传、会话、请求默认值或叠图行为。方法和证据格式见[高级配置验证](reports/advanced-options/README.md)，本轮三场景 Windows 运行见[整合验证记录](reports/windows-latest-20261023.md)。

## 本次兼容修复

| 问题 | 处理 |
| --- | --- |
| 启动脚本写死 POSIX Python 路径 | 用 Node 入口查找当前平台的解释器 |
| Windows 查询 PID 可能误杀进程 | 使用系统句柄查询存活状态 |
| 取消后残留 FFmpeg 子进程 | 终止本应用 worker 的进程树，隐藏子进程窗口 |
| 重复实例共享端口 | Windows 使用独占监听 |
| 默认编码导致中文配置、结果或错误读取失败 | 请求、配置、结果与日志显式使用 UTF-8 |
| 中文路径生成缩略图失败 | OpenCV 编码后由 Python 写入文件 |
| `.mjs` 被系统映射为 `text/plain`，按钮不可用 | 前端桥模块使用 `.js` |
| Windows ASS 文件路径导致叠图滤镜失败 | 按 FFmpeg 滤镜语法转义字幕文件路径 |
| 自动球场标定向中文目录写图失败 | 改用 OpenCV `imencode` 后由 Python 写入文件 |
| 基准运行退出后遗留后端或 worker | 按进程树终止该次基准启动的进程 |
| 正常关闭租约与任务结束并发，被记为异常 | 区分正常关闭与实际连接失败，收尾时等待租约任务结束 |

流复制 MP4 的预滚帧数差异另见[媒体输入说明](../../modules/media/README.md#帧与时间)。

## 验证与范围

```powershell
npx --yes pnpm@9.15.9 run test:backend
npx --yes pnpm@9.15.9 run typecheck:frontend
git diff --check
```

此前三个场景的 Windows 实测摘要见[2026-10-20 运行记录](reports/windows-runtime-20261020.json)，个人视角 CPU/CUDA 对照及当时的默认 CUDA 应用流程见[2026-10-21 性能报告](reports/pose-performance-20261021.md)。记录对应当时的源码、工作区和配置；负责人在 macOS/MPS 上的新性能报告也不能直接当作本机 Windows/CUDA 的验收结果。

本轮后端检查、前端配置检查、类型检查与构建通过。已通过真实 HTTP 流程完成 A/C/D 三短片识别及成片生成：高视角使用四项默认配置并开启球路，场边和个人视角使用前三项配置、关闭粗筛；个人视角实际使用 CUDA、batch 1。完整媒体解码和画面复核的结论以[本轮报告](reports/windows-latest-20261023.md)为准。

本轮默认配置与旧 CPU 测量不同，不构成新的 CPU/CUDA 配对收益；旧通过数和耗时也不沿用。三短片运行不代表独立来源准确率、球路落点精度或长视频验收完成。

当前支持 Windows 源码开发与运行。`build:product` 的发行脚本仍要求 macOS Apple 芯片，尚未提供 Windows EXE 或安装包。macOS / Linux 的解释器路径仍受入口支持，本次没有在这些系统重新运行验证。
