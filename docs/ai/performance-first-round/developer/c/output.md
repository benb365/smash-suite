# C 线开发第 1 轮交付

## 实现

OPT-03 在 [predictor.py](../../../../../modules/models/tracknet/predictor.py) 为显式传入帧 ID 的调用加入容量为 3 的 LRU 缓存，只保存单帧 CPU 预处理张量。RGB 转换、`copy`、通道转换、float/255 和 antialias resize 顺序在阶段 03 保持原样；拼接、模型调用、候选解码和每组帧顺序不变。`recognize.py` 仅在 `courtside`/C 路径传入 `frame_id`，片尾沿原逻辑推理并复用输入；`personal`/D 与没有帧 ID 的调用不启用缓存。C 观测结束或异常退出时清空缓存，峰值统计由 predictor 清理方法记录。

OPT-04 只删除 TrackNet 中 `rgb.copy()`。在 OpenCV 转换输出上检查到数组独立持有内存、C 连续、与输入不共享内存；copy 前后的预处理张量严格相等。真实短片与真实模型的逐帧检查已放入主控探针，尚未运行。

统计新增 `tracknet_cache_hits`、`tracknet_cache_misses`、`tracknet_cache_prepared_frames` 和 `tracknet_cache_max_items`；既有 `tracknet_input_frames` 仍按每次模型调用的全部输入帧累计。

## 文件与补丁

产品源码只涉及 `modules/models/tracknet/predictor.py` 和 `modules/rally/recognize.py` 的 `observe` 函数。定向模拟测试在 `modules/models/tracknet/tests/test_preprocessed_cache.py`；真实帧探针在本目录的 `probe_real_inputs.py`。

按以下顺序应用独立产品源码补丁：

1. `c03-cache.patch`：任务基线到 OPT-03。
2. `c04-copy.patch`：OPT-03 到 OPT-03 + OPT-04。

`stage03.sha256` 和 `stage04.sha256` 记录各阶段两个产品源码文件的 SHA-256。补丁不包含测试、文档或 `person_signals`。

## 检查

- `modules/models/tracknet/tests/test_preprocessed_cache.py`：2 项通过。使用模拟模型覆盖指定重叠窗口、缓存不超过 3 项、命中帧输入严格同值同序、尾部补推理与 shifted 序列、C 任务清理，以及 personal/D 无帧 ID/无清理。
- `py_compile`：predictor、recognize 和真实探针通过。
- `git diff --check`：通过。
- 合成 uint8 图像的 OpenCV 数组检查：转换结果独立、连续且不与输入共享内存；copy 与不 copy 的 float/255/resize 张量严格相等。真实帧检查留给主控探针。

模拟检查不代表真实模型效果或完整产品验证。

## 探针修正与未运行项

主控首次运行的真实探针中，4 组模型热图和候选均严格相等；`tensor_matches` 全为 false 是探针形状错误：录制值为 `9×288×512`，参考值为 `1×9×288×512`。现已将比较改为同形状的 `reference_batch[0]`，并在 JSON 中保存每组两侧形状，仍使用 `torch.equal` 严格比较。首次 JSON 由主控保留，本修正不覆盖；请主控另存并串行运行第二次结果。

本角色没有运行真实模型、真实视频探针、完整基准或全量 backend 测试。探针接收 task.md 指定的已准备权重、固定短片和原版 predictor 源文件路径；还会报告缓存张量实占、约 5.1 MiB 理论本体及模型加载前后进程峰值。

仍需主控确认修正后的张量严格等价、真实内存峰值以及 C-short 单项结果。未据模拟或首次形状误报宣称产品效果通过。
