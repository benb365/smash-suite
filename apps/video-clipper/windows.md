# Windows 环境与启动

在 Windows 上从源码运行自动剪辑应用，使用 Chrome 或 Edge 操作本机服务。本说明适用于 Python 3.11、Node.js 20.19+；命令在仓库根目录的 PowerShell 中执行。

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

TrackNet 和 YOLO 沿用现有设备选择规则。个人斜侧方场景中的姿态估计仍在 CPU 上运行，不能用 CUDA 可用来推断整个任务都在 GPU 上执行。

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

流复制 MP4 的预滚帧数差异另见[媒体输入说明](../../modules/media/README.md#帧与时间)。

## 验证与范围

```powershell
npx --yes pnpm@9.15.9 run test:backend
npx --yes pnpm@9.15.9 run typecheck:frontend
git diff --check
```

检查结果和此前三个场景的 Windows 实测摘要见[运行记录](reports/windows-runtime-20261020.json)。此前端到端录像验证使用包含本地验证工具的工作区；该记录将其与整理后分支的检查分开列出。

当前支持 Windows 源码开发与运行。`build:product` 的发行脚本仍要求 macOS Apple 芯片，尚未提供 Windows EXE 或安装包。macOS / Linux 的解释器路径仍受入口支持，本次没有在这些系统重新运行验证。
