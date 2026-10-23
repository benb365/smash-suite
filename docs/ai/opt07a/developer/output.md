# 第1轮开发交付

第1轮返工，按主控小样结果撤回 fused 生产转换，只保留原地归一化。实现基线：`develop` `94a8465946f97610d91c2bb75b6b9930a93650e5`；交付位于 `codex/opt07a-tracknet` worktree。本轮实际源码 SHA256：

| 文件 | SHA256 |
| --- | --- |
| `modules/models/tracknet/predictor.py` | `d8208470e973ff4388d8c34be54f19609a50a61571e72aaa3ed45dcaf8c34152` |
| `modules/models/tracknet/tests/test_preprocessed_cache.py` | `24a089cf9d4cc38aba0a0c14e77b0c4e0755a744503f63f3123d6128d5137b69` |
| `docs/ai/opt07a/probe.py` | `a60ffde2f8b1d140428b746354e47ed2a72dca4045c97a87aae3f5f3e18aa101` |
| `docs/ai/opt07a/recognition.py` | `030f8ff03186a1f97d3350a975f6daf63fb779467a998e1bf0061797bee0f428` |

## 改动

- TrackNet 恢复 `cv2.cvtColor`，保留 `.float().div_(255)` 原地归一化；缩放和 antialias 设置不变。fused 转换没有留在生产代码。
- 参数化回归使用非均匀颜色的非连续 uint8 裁剪视图，普通调用和重叠缓存都逐值比较原公式的模型输入，并检查输入未变。
- `probe.py` 现在构造 baseline、inplace、fused 三个互异实验类，并核对 current 生产类与 inplace 公式相同。对三种实验和当前生产实际 batch、热图、球点、候选及缓存状态作严格比较；模型输入和热图原样存入 `model-io.pt`。
- 新增 `recognition.py`，支持独立进程的 baseline/candidate、A-short/C-short 识别。校验输入与已缓存权重、强制 MPS、设置 torch/OpenCV 线程数，保存识别结果、导出区间、统计、进程采样和代码/环境元数据；不调用模型下载或视频导出。

## 验证与边界

- `python -m pytest -p no:cacheprovider modules/models/tracknet/tests/test_preprocessed_cache.py -q`：4 passed。
- `python -m py_compile ...` 覆盖本轮 Python 源码与测试；通过。编译缓存写入 `/private/tmp`。
- `git diff --check`：通过。
- 在不构造模型的情况下调用 `probe.build_variants()`：动态注册成功，冻结版 SHA 与批准值一致，baseline、inplace、fused 公式互异，current 与 inplace 公式相同。
- 调用路径核对显示 `FileFrameSource` 输出 `bgr24`，其他现有视频调用使用 OpenCV 解码帧；已确认的运行输入为 uint8 三通道 BGR，没有发现另一个合法 dtype 契约。
- 主控小样证据显示：单张真实 A-short 首帧、18 组测量的预处理中位数为 baseline 1.775 ms、inplace 1.670 ms、fused 5.426 ms；fused 约为 baseline 的 3.06 倍。Profiler 显示 `.div` 分配 24,883,200 字节、`.div_` 为 0。该证据不代表稳定整段提速或进程峰值；据此撤回 fused 生产方案。
- `preprocess-small.json` 实际记录 `torch=4, opencv=18`，与返工 input 文字中的 OpenCV1 不一致；本轮只采用小样中的相对候选排序，不声称该结果验证了 OpenCV1 配置。
- 未执行真实模型、MPS、A/C/D 等价探针或识别耗时；由主控串行运行并独立验收。本交付不构成真实模型验收结论。

## 此前交付记录

首版曾将 fused 方案用于生产，源码 SHA256 为 `fa19748811ec51484bcb1f97241899da1c60a6f9972c8ceb80ea58180b1bd83c`；聚焦回归为 4 passed，动态加载自检通过。该版本按上方小样证据撤回。`recognition.py` 保持未变（SHA256 `030f8ff03186a1f97d3350a975f6daf63fb779467a998e1bf0061797bee0f428`）。

## 第1轮收尾补记

按主控文档状态指令，将专题 README 的 OPT-07A 状态从“正在独立任务分支验证”改为“已在任务分支完成，待人工确认”。未改实现、测试、应用报告或其他文件；未运行验证。主控将冻结该文档并安排验收方复查。
