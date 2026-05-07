# Smash Suite

Smash Suite 是一个本地优先的自动化羽毛球视频套件。当前仓库已有 PC-only 的测速 baseline；下一阶段 demo 目标是用 Android 手机作为智能摄像头节点降低回传数据量，由 PC 完成控制、标定、测速、结果展示和导出。

## 快速接手

- 想粗略了解项目：读完本 README 即可知道产品目标、当前 baseline、技术栈和运行方式。
- 想继续开发：先读 [AGENTS.md](AGENTS.md)，再从 [docs/plan/roadmap.md](docs/plan/roadmap.md) 顶部的 `Current Focus` 开始。
- 想深入产品和架构：读 [docs/features.md](docs/features.md) 和 [docs/architecture.md](docs/architecture.md)。

## MVP（Minimum Viable Product） 目标

- Android 阶段性只负责高帧率采集、粗场景识别和片段上传，不做业务 UI。
- PC 是唯一产品入口和控制中心，负责设备控制、场地标定、测速分析和结果展示。
- 固定单机位，通过球场关键点完成平面标定。
- 当前 PC baseline 可读取本地视频文件路径或摄像头输入，视觉分析在本机完成。
- 先用 OpenCV 传统视觉 baseline 跑通 Android 片段到 PC 测速闭环，再预留模型检测器接口。
- PC Web UI 展示设备状态、标定、速度曲线、轨迹点、关键帧和导出结果。
- Demo 阶段速度趋势可用，目标误差不高于 20%。

## 技术栈

- Frontend: Vite, React, TypeScript
- Backend: FastAPI, WebSocket, Pydantic
- Vision: OpenCV baseline, homography 标定, 轨迹差分测速
- Storage: 本地 `data/` 目录保存会话、导出结果和关键片段

## 项目结构

```text
.
├── backend/              # FastAPI 服务与视觉处理管线
│   ├── app/
│   │   ├── api/          # REST 和 WebSocket 路由
│   │   └── vision/       # 标定、采集、跟踪、测速
│   └── tests/            # 后端单元测试
├── frontend/             # React 场边测速界面
├── data/                 # 本地会话、样片和导出结果
├── docs/                 # 目标、功能、架构与作战手册
│   └── plan/             # 计划手册、里程碑路线图和执行记录
└── models/               # 后续检测模型目录
```

## 运行方式

安装依赖：

```bash
pnpm install
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
```

启动后端：

```bash
pnpm run dev:backend
```

启动前端：

```bash
pnpm run dev:frontend
```

默认前端访问 `http://localhost:5173`，后端访问 `http://localhost:8000`。

## 当前工作流

1. 在 Web UI 创建会话。
2. 输入四个球场角点对应的画面坐标，并保存标定。
3. 输入本地视频文件路径，或选择本地摄像头索引。
4. 后端 worker 在本地读取帧、检测高速运动候选、生成轨迹和速度样本。
5. 前端通过 WebSocket 接收速度样本并绘制曲线。
6. 分析完成后在 `data/exports/` 生成 JSON 和 CSV。

## 重要限制

- 单目平面标定无法完整还原羽毛球高度，当前读数是固定机位 demo 级估计。
- 60fps 视频可以运行，但高速杀球误差会明显上升；建议 120/240fps。
- 当前 baseline 适合固定机位和清晰背景，真实场馆泛化需要后续接入微调检测模型。
- 本机需要安装 OpenCV Python 包才能处理真实视频或摄像头输入。

## 后续路线

文档入口见 [docs/README.md](docs/README.md)。当前优先级、里程碑状态、证据和阻塞以 [docs/plan/roadmap.md](docs/plan/roadmap.md) 为准。

## 其他
Assistant by Codex & Copilot
