# 独立验收 · 轮次1

## 职责与冻结版本

只在 `/Users/bytedance/.codex/worktrees/trajectory-overlay-v1/smash-suite` 验收，分支 `codex/trajectory-overlay-v1`，基线 `94a8465`。读取本文件、`../task.md`、仓库指引及必要实现/正式报告；不得读取developer通信目录。只写自己的output和临时证据，不改实现或标准。实现已停止；主控发出开始信号时产品证据也已完成。

先核对 `freeze.json` 全部代码哈希，当前合成摘要为 `97211e8ad2295e84a44aff405b989855534910ca6fe5dfd1192796a958536853`。任何不符立即反馈。报告必须分别给功能、代码、文档结论，标明轮次、版本和未执行内容。不能采用旧版本“通过”代替当前检查。

## 用户批准的首版标准

- 固定高视角单打，两份真实输入自动标定，复用真实找球观测，输出每拍二维起点/终点及来源；模块独立，产品烧录小球场。
- 被接回也尝试预计落点；不可靠时用户允许下一次击球位置或实际落地点代替，统一箭头样式，诊断必须区分来源。证据不足不得造点，未解析无箭头。
- 高视角默认开启、上传配置可关闭；固定右上角、高约画面30%、白场线/深色半透明底/统一箭头。每拍替换、不保留历史，回合结束清除，补时不残留旧箭头。只展示平面坐标。
- 首版实际效果粗检，不预设量化精度门槛：独立观看连续回合和失败窗口，判断场地、方向、起点选手、漏拍、跳变是否有明显错误。不能凭预测计数或像素残差宣称准确率通过；若明显错误应明确判不通过并给具体案例。
- 时间映射与剪辑边界、关闭行为、音画偏移、非零首PTS、VFR必须验证；箭头切换不超过一源帧。
- 任务之外的其他视角、公开发行、下载新模型、推送/集成都不在范围。

## 真实输入、缓存与证据

两输入是 `datasets/badminton-v1/local/rally/` 下的 `m1-short-a1-01-20261015/clip.mp4`（A1，4200帧、首PTS91ms）和 `m1-a2-01-20261019-workerfix/clip.mp4`（A2，2421帧、首PTS0）。哈希和模型哈希在 `modules/trajectory/.runtime/round1-evidence.json`。

对应 `modules/trajectory/.runtime/<样本名>/` 有真实球点jsonl/meta、rallies、人物观测、court、校准图、shot-paths。A1当前35拍（predicted14/next_hit16/detected4/unresolved1），A2为23拍（11/10/1/1）。用户最新询问并获确认可直接用历史球点工作；不要为了复核重跑TrackNet或YOLO，不下载、不改依赖或锁文件。需要复算用 `python -m modules.trajectory analyze` 和同目录人物缓存。核对缓存来源/完成状态，别把模拟测试称作真实效果。

正式算法报告 `modules/trajectory/reports/trajectory-overlay-v1.md`、产品报告 `apps/video-clipper/reports/trajectory-overlay-v1-product.md` 包含复现与证据路径。最终产品报告稍后列出复用当前真实结果导出的双样本MP4及指纹。早先真实API输出是在分析代码变化期间运行，仅作联调诊断；不能当作最终冻结版本一次完整API运行。判断现有组合证据是否足以证明实际链路，存在疑点明确列出；不得偷换为“全流程单次重跑通过”。

重点连续窗口：A1首回合3.6–9.6秒；A1 24.64–28.48长漏点；A2 49–54秒；A2 73.92–76.12长漏点和79.88–87.2秒。A1尾拍108.72s和A2尾拍87.16s为unresolved。结合真实源画面和最终成片判断长漏点合拍是否破坏基本效果，不能仅复述开发报告。

使用仓库 `review-video-results` 技能和其固定查看器展示实际区间，现有 `modules/trajectory/.runtime/review.json` 和 `http://127.0.0.1:54363/` 可核实后复用。不得另造HTML。需要浏览器请走cua工具；读取视频帧可用已有媒体工具。主控UI实测默认开启、点击关闭、其他视角隐藏、回到高视角开启；截图 `/tmp/trajectory-ui-default-on.png`。独立检查前端与请求代码，必要时用现有UI页 `http://127.0.0.1:53507/` 验证，不重新上传素材或启动模型任务。

## 独立工程与文档检查

主控补充的最终证据路径：`.runtime/trajectory-overlay-v1-product/results/frozen-offline-replay/summary.json`，两个子目录为 `a1/`、`a2/`，各有 `output.mp4`、`export-evidence.json`、`trajectory-overlay.ass`、实际帧、输入结果副本；`review.json` 可用统一查看器播放。主控已核对当前shot-paths摘要与round1一致；A1成片46420ms/A2为25980ms，均有原声音，且模型重跑标记为false。产品角色只在补写报告/通信材料，所有实现均冻结；文档阶段请使用其补齐后的正式报告，如仍旧写“算法调整中、第二样本未完成”，应报告文档陈旧而不擅改。不需要在原始API诊断目录继续找最终版本。

运行当前后端测试、前端类型/构建、文档构建、`git diff --check`，必要时将机械命令分配给低成本模型独立子任务。`.venv` 和 node_modules 是已安装依赖的忽略符号链接；不要安装新依赖。全局pnpm在进入脚本前被原有watchpack@2.6.3的release-age元数据阻断，不能改策略，直接等价入口如下：

```sh
.venv/bin/python -m pytest
# 前端目录
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/rspeedy build
./node_modules/.bin/rsbuild build --config host.config.ts
# tools/docs-site 目录
./node_modules/.bin/vitepress build
```

默认沙箱不能写任务worktree/枚举macOS进程，需要时使用已授权任务的escalated命令，说明用途；不要把环境限制当产品测试失败。检查开关关闭时回合算法/渲染未变、缓存验证、实际ASS烧录、边界映射及异常处理。阅读新增模块及受影响入口的人类文档，报告是否准确、职责明确、无过度声称。最终状态由主控在通过后改成待人工确认，届时需再核对这部分文档及不变代码摘要。
