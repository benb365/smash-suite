# 用户授权：独立提交主目录原有文档调整

用户刚明确“主目录的修改可以顺手帮我 commit”。主控已承诺单独提交，与已完成基线集成分开，outputs本地产物不纳入。本任务执行目录 /Users/bytedance/workspace/experiments/smash-suite，develop 当前应为4dc29706165b5a85bae94097b47359f05aaf9ff4。不要读其他角色通信，仅读本input、实际diff、你自己先前生成的integration备份/manifest。

基线集成已完成且你已恢复原文档修改。无需重新stash/合并/恢复或改基线。检查当前git status，精确核对九份原始文档调整：README.md、apps/video-clipper/README.md、docs/README.md、modules/media/README.md、modules/models/README.md、modules/models/keypoint_rcnn/README.md、modules/models/tracknet/README.md、modules/models/yolo11n/README.md、modules/rally/README.md；roadmap现在已完成且干净，不重新改。两README在新HEAD上应只有原锚点#开发工作流→#开发环境；其余七份字节应等于你已有备份。若有额外不明变更先回报。索引开始应为空。

审查以上九文件diff，保留用户调整完整内容，不自行删改。git diff --check；文档新本地链接尤其#开发环境应检查目标标题存在，不安装依赖，不因文档重复产品测试。只明确暂存以上九paths，检查暂存diff/stat无其他文件，提交 docs: clarify development setup and module guidance。禁止git add -A、push、删worktree、读写暂存outputs、改模型/样片/锁文件/凭证。

本input及你自己的输出commit-main-docs-output.md是本次流水，可一并暂存docs/ai/performance-baseline/这两个明确paths；提交前写简短已执行检查（不用填未知SHA），提交后通过最终工具消息给真实SHA/分支/状态，不追写文件制造脏尾巴。来源任务worktree/correction/input-integrate.md若稍后出现主控补充授权，只是同一用户授权的重复同步，不重复执行。

提交后develop应包含基线merge与独立文档提交，已跟踪文件干净、索引为空，仅保留最初outputs/未跟踪；保留所有原始证据和任务worktree。完成后停止写入并回报真实提交SHA及检查。
