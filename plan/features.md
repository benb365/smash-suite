# Smash Suite 项目初始化与需求实施计划

## Summary

- 在当前目录初始化项目文档与工程骨架。
- 在 `plan/` 文件夹保存项目计划。
- 新建根目录 `README.md`，说明项目目标、架构、运行方式和当前 MVP 范围。
- 按 MVP 路线搭建本地 Web Demo：前端 UI、FastAPI 后端、OpenCV 视觉测速管线。
- 架构和长期整体规划单独维护在 `plan/architecture.md`，用于描述产品级模块拆分与演进方向。

## Initial Files

- `README.md`
  - 项目简介：自动化视频羽毛球测速。
  - MVP 目标：固定机位、手机高帧率、本地准实时处理、速度曲线展示。
  - 技术栈：React/Vite、FastAPI、OpenCV、WebSocket。
  - 运行架构：本地摄像头/视频输入、本地视觉 worker、Web UI 实时显示。
  - 准确性目标：demo 阶段趋势可用，误差目标不高于 20%。
- `plan/features.md`
  - 保存完整项目计划。
  - 包含阶段拆分、接口设计、视觉算法路线、测试策略、风险与假设。

## Implementation Steps

### 初始化仓库结构

- `frontend/`：Vite + React + TypeScript。
- `backend/`：FastAPI + Python 服务。
- `backend/app/vision/`：采集、关键帧、跟踪、测速模块。
- `data/`：本地会话、样片、导出结果。
- `models/`：后续检测模型目录。

### 第一阶段：离线 Demo

- 选择本地视频文件路径，后端直接读取，不上传完整高帧率文件。
- 在 Web UI 中手动输入或采集球场四角标定点。
- 用 OpenCV baseline 跟踪羽毛球高速运动候选。
- 输出速度曲线、轨迹点、关键帧事件和 CSV/JSON。

### 第二阶段：准实时

- 支持本地摄像头输入。
- 使用 ring-buffer 保存疑似击球前后短片段。
- 通过 WebSocket 推送速度样本和关键帧事件。
- UI 显示当前速度、速度曲线、会话状态和导出结果。

### 第三阶段：准确性增强

- 增加人工标注样片和 golden video 测试集。
- 接入 YOLO/其他检测模型适配器。
- 对比传统 baseline 与模型检测效果。
- 调整平滑、异常点过滤、置信度和断点策略。

## Interfaces

### REST API

- `POST /api/sessions`：创建本地测速会话。
- `GET /api/sessions`：列出会话。
- `GET /api/sessions/{id}`：读取单个会话状态。
- `POST /api/sessions/{id}/calibration`：保存球场标定。
- `POST /api/sessions/{id}/run`：启动本地视频或摄像头分析。
- `GET /api/sessions/{id}/results`：获取轨迹、速度曲线、关键帧和导出文件。

### WebSocket

- `/ws/sessions/{id}`：推送 `session_status`、`trajectory_point`、`speed_sample`、`keyframe_event` 和 `analysis_error`。

### Core Types

- `CalibrationConfig`：image points、world points、fps、court profile。
- `TrajectoryPoint`：frame id、time ms、pixel point、world point、confidence。
- `SpeedSample`：time ms、speed km/h、confidence、source frame range。
- `KeyframeEvent`：time ms、frame id、reason、confidence、optional clip path。

## Test Plan

- 单元测试：标定、轨迹差分、速度计算、异常点过滤。
- 集成测试：本地视频输入到速度曲线输出。
- E2E 测试：Web 创建会话、标定、运行分析、查看结果、导出数据。
- 性能测试：120/240fps 样片下验证本地处理延迟和 UI 推送稳定性。
- 准确性测试：用人工标注样片验证速度误差目标不高于 20%。

## Assumptions

- 第一版使用固定单机位。
- 主要输入为手机 1080p 120/240fps 视频或本地摄像头。
- 不上传完整高帧率视频，视觉分析尽量在本地设备完成。
- Demo 主展示速度曲线，同时支持场边准实时速度读数。
