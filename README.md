# Smash Suite

Smash Suite 是一个本地优先的自动化羽毛球视频套件。第一版面向固定机位、手机高帧率视频或本地摄像头，目标是在场边准实时显示羽毛球速度曲线，并避免上传完整 120/240fps 视频。

## MVP（Minimum Viable Product） 目标

- 固定单机位，通过球场关键点完成平面标定。
- 本地读取视频文件路径或摄像头输入，视觉分析在本机完成。
- 先用 OpenCV 传统视觉 baseline 跑通端到端流程，再预留模型检测器接口。
- Web UI 通过 WebSocket 展示实时状态、轨迹点、速度曲线和当前读数。
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
├── models/               # 后续检测模型目录
└── plan/                 # 项目计划与路线图
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

完整实施计划见 [plan/features.md](plan/features.md)。

长期整体规划与架构设计见 [plan/architecture.md](plan/architecture.md)。

## 其他
Assistant by Codex & Copilot
