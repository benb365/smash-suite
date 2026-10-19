# 整理后快速检查与开发环境调整

日期：2026-10-19。当前状态看[路线图](../../plan/roadmap.md)，本目录保存检查流水与原始输出，不加入人类文档站。归档日志仅清理行尾空白和多余末尾空行，以通过 Git 格式检查。

## 用户确认的范围

- 确认整理后的环境、模块导入、已有自动测试、保存观测回放和应用入口。
- 耗时任务能够进入执行即可；不运行真实模型、长片评估、性能测量或产品重新打包。
- Python 兼容下限调整为 **3.9+**，建议使用 3.11；不能锁定为仅支持 3.9。
- 素材采集工具单独保留 Python 3.10+ 和独立环境。
- README 集中说明最低工具版本，示例按版本要求安装；删去开发安装与应用打包的冗余解释。

## 检查结果

| 项目 | 实际结果 | 原始记录 |
| --- | --- | --- |
| 环境 | Python 3.9.6，Node.js 22.22.2，pnpm 10.33.0 | [环境](python/versions.log)、[Android 环境](frontend-android/android-versions.log) |
| Python 语法 | 83 个维护文件逐个编译，0 失败；不执行源码，不生成 pyc | [语法结果](compatibility/compile-results.txt) |
| 模块导入与帮助 | 15 项导入、5 个命令帮助入口通过；配置有效、3 份报告及 3 个模型权重路径存在，只检查文件未加载权重 | [导入汇总](imports/summary.json) |
| 模块与后端测试 | 安装前、安装后均为 92 passed | [首次测试](python/test-backend.log)、[安装后测试](installation/test-backend.log) |
| 保存观测回放 | 16/16 完全一致，不运行模型 | [回放输出](replay.json)、[回放日志](python/replay.log) |
| 剪辑前端 | TypeScript 检查、静态构建通过 | [类型检查](frontend-android/typecheck-frontend.log)、[构建](frontend-android/dev-frontend.log) |
| Android UI | TypeScript 检查通过 | [类型检查](frontend-android/android-ui-typecheck.log) |
| Android 原生入口 | 离线 Gradle help、assembleDebug --dry-run 通过；仅解析任务，未生成 APK、未连接设备 | [Gradle help](frontend-android/gradle-help-escalated.log)、[任务解析](frontend-android/gradle-assemble-dry-run.log) |
| Android 接收端 | 首页、健康接口均 200，本地 FFmpeg 找到，SIGINT 退出 0 | [启动结果](receiver/result.json) |
| 接收端自动测试 | 8 项通过，约 7 秒；仅使用内存数据和临时生成的短媒体 | [测试记录](receiver-tests/) |
| 开发安装 | 项目安装成功，metadata Requires-Python 为 >=3.9；backend 目录清除 PYTHONPATH 后可直接导入 modules 与 app.main | [安装日志](installation/install-final.log)、[导入结果](installation/backend-imports-after-install.json) |
| 剪辑实际入口 | 清除 PYTHONPATH，用 pnpm run dev:backend --no-browser --port 0 启动；健康接口、首页均 200，浏览器首页正常显示；SIGINT 后退出 0，临时 process 目录已清空 | [HTTP](clipper/http.json)、[浏览器](clipper/browser.json)、[停止清理](clipper/shutdown.json) |
| 文档检查 | VitePress 构建通过，58 个页面；首页环境要求、素材采集环境锚点存在，未生成 docs/ai 页面 | [最终检查](final-check/) |

## 安装问题与处理

1. 旧 `.venv` 没有安装仓库包。从 `apps/video-clipper/backend` 启动时出现 `ModuleNotFoundError: No module named 'modules'`。pytest 自带根路径配置，测试通过没有覆盖实际开发启动命令。
2. 最初临时设置 `PYTHONPATH` 指向仓库根目录后服务与首页可启动。这使用仓库现有源码，没有下载额外的模块包，也不是对业务代码的修复。
3. 当时项目声明 `==3.11.*`，现有环境为 3.9.6。用户确认后将声明改为 `>=3.9`，Ruff 语法目标改为 py39；移除 `.python-version` 单版本固定。
4. 实际安装时，pip 21.2.4 不支持这个 pyproject 项目的可编辑安装。构建后端最低版本改为 setuptools>=64，提供标准可编辑安装支持；没有添加 setup.py 或路径兼容代码。
5. 本轮执行中 pip 已由 21.2.4 更新到 **26.0.1**。随后用户指出不应直接升级，而应写明所需版本。最终 README 明确 **pip 21.3+**，命令改为 `pip install 'pip>=21.3'`，不使用 --upgrade。该最终命令已验证，现有 26.0.1 满足要求，执行后版本未变。没有继续升级或回滚工具。
6. 开发安装新增 ruff 0.17.1 和本地 editable smash-suite 0.2.0，冻结清单中的原有 73 项版本不变。构建隔离环境独立解析 setuptools，不把它的临时构建工具算成运行环境升级。详见[版本对比](installation/version-comparison.json)。
7. 安装后已移除临时 PYTHONPATH，实际启动命令通过，不再以“补路径后可运行”作为最终启动结论。尚未从全新空环境重建所有依赖。

相关官方依据：[pip 21.3 的 PEP 660 支持](https://pip.pypa.io/en/stable/news/#v21-3)、[setuptools 64 的可编辑安装支持](https://setuptools.pypa.io/en/latest/userguide/development_mode.html)。

## 独立工具与文档调整

- 素材采集工具由 `.agents/skills/curate-badminton-training-data/scripts/run.py` 管理自己的 `.venv`，入口要求 Python 3.10+，其中 yt-dlp 当前也明确要求 CPython 3.10+。保留入口、技能要求和历史采集报告的原版本；没有搜索或下载素材、执行采集或更改该环境。
- 根 README 和数据集 README 明确该例外；Android 接收端已在 3.9.6 启动并通过 8 项测试，其说明改为 3.9+。
- 根 README 标明 Python 3.9+、建议 3.11。架构图使用内置 imagegen，仅将底部版本改为 Python 3.9+，提示词保留在 docs/assets/architecture-prompt.txt；历史提示词不批量改写。
- `.gitignore` 排除开发安装生成的 `*.egg-info/`，没有改业务逻辑或产品依赖版本。

## 非阻塞提示与未覆盖项

- 受限沙箱不能绑定本机回环端口，网络安装首次也受限；相同检查在允许本机/网络访问后通过。保留首次失败日志，不将沙箱限制视为源码错误。
- 旧环境有 urllib3/LibreSSL 提示；前端构建有 browserslist、ObjectRef 提示，文档构建有大 chunk 提示，未阻止本次检查。
- 首次浏览器访问曾记录 MutationObserver 参数异常；安装后复核未复现，只剩初始化参数弃用提示。源码未因此修改，仍需在完整产品流程中观察。
- 最初通过 pnpm/管道整体 Ctrl-C 后包装命令退出 1，临时 work 中留下空 process 目录；最终向本次服务进程发送 SIGINT，命令退出 0，work 已清空。没有把第一次的包装命令退出直接归因于产品缺陷。
- 本次没有复测真实模型、录像识别效果、长片性能、导出预览保存完整流程、阶段耗时界面、新发行包或 Android 真机能力。
- Python 3.11 仅为建议版本，本次实际验证环境为 3.9.6；不声称所有更高版本都已实测。
- 不改变 A/C/D 算法效果验收结论，不重新打包，也不把旧测试包结果用于新源码。

## Git 范围

开始时仅有未跟踪的 backup/；保持原样，没有暂存、提交或推送。本任务仅调整环境声明、环境相关说明、架构图、忽略规则及检查记录，唯一 Python 源文件改动是接收端版本说明字符串。
