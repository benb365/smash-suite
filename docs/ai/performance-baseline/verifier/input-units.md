# 第四轮：表格单位独立文档复验
在原worktree /Users/bytedance/.codex/worktrees/performance-baseline/smash-suite 继续。不读其他角色通信。用户要求“表格的单位标注一下”，本轮只改报告五张数值表的表头，其他正文/数据行/程序/资源图不变。
冻结：HEAD 15182e8bc9007934ae4d2b44bb4515317cf9e8be；唯一允许的已跟踪文件差异apps/video-clipper/reports/performance-baseline.md，SHA256 7ed39239fa4fe4ce793f9ef7d1fed5c5f66eb5747a8a0e98c446338cedfbf610。主控/开发停止写入。独立首尾重算SHA并核对git diff只有五个表头行。
检查：全部时间列秒、速度倍、成片段数段、RSS GiB、CPU百分比、MPS MiB与采样间隔秒；Python计数样本/错误次数；原生混合列样本数与权重秒、事件数与配对裁剪并集秒分别正确，PID/UID无需物理单位；全部7表列数正确且所有数据行与HEAD逐字相同，无无关修改。git diff --check。只改单位无需产品测试、模型/媒体/采样，不安装或鉴权。若无实际渲染验证，明确源码检查边界。
只写verifier/output-units.md，短列本轮4、HEAD、实际SHA、功能/代码沿用未变证据、文档结论与检查，完成停止写入。不修改实现/报告/标准，不提交推送集成。通过后主控按已授权流程本地提交报告与小执行记录。

主控更正：此前复制开发记录中的完整HEAD有一处字符顺序错误；本行HEAD已直接从git rev-parse HEAD读取校正。报告SHA与实现内容均未改变。请继续本轮核对。
