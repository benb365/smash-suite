# OPT20 第1轮开发：最小静态删除

唯一工作树按task路径/分支，只读本input/task、必要README/源码和primary指定baseline，不读任何verifier通信目录。按task删除Farneback及专属状态/提取/传递，仅改recognize.py、players_v2.py、trials.py及删body_features.py；同步需要的所属稳定文档，不能改task/标准，不推进其它优化，不留body_motion=None兼容。先核对真实活跃caller/consumer，已有规则、selected人物、Pose/PyrLK完全不动。后端全量和真实D复跑为必要验证；纯死数据删除不新增镜像实现或测试个数凑数，若发现现有契约真正缺关键覆盖再说明。

当前09A独立模型复跑与09B代码准备并行，本阶段只写最小源码/文档及自己的output，允许轻量语法/diff检查；暂不跑pytest、pnpm、视频/模型/权重或下载。输出精确diff/SHA、静态数据流证据和待执行检查后暂停，主控稍后释放测试/真实运行。托管worktree写入及产生文件的命令用exec_command require_escalated（已授权隔离任务），不能改ROOT/REPORT到tmp伪装来源。完成不提交不推送不合入。
