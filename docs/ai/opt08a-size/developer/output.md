# OPT-08A 第1轮开发输出

实现位于 `docs/ai/opt08a-size/run.py` 和 `docs/ai/opt08a-size/test_run.py`。入口逐一断言 resize 参数和输出坐标映射表达式在当前 TrackNet 源码中各出现一次，派生后在独立模块中、`recognize` 导入之前绑定候选类。每次调用记录帧数、frame_ids 与 points 的坐标和置信度；入口复用 OPT-07A 的 MPS/缓存权重校验、完整识别、统计、进程采样和导出区间流程，随后补记尺寸、派生类、派生源码及 runner 哈希。

运行方式：

```sh
.venv/bin/python docs/ai/opt08a-size/run.py \
  --size 288x512 --case A-short \
  --models apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models \
  --output apps/video-clipper/.runtime/opt08a-size/A-short-288x512
```

`--size` 可选 `288x512`、`216x384` 或 `144x256`；`--inputs` 默认使用 performance-first-round 清单。输出目录需尚不存在。原 helper 的内部 `baseline` 标记用于触发派生源码动态绑定，完成后 `run.json` 明确记录实际 `size_candidate`，并保留 `helper_reported_variant` 供追溯。

定向验证：`pytest -p no:cacheprovider -q docs/ai/opt08a-size/test_run.py` 通过（3项）；`python -m py_compile` 与 `git diff --check` 通过。测试用合成帧和 stub model 验证三种合法输入尺寸、288×512控制与原路径点值相同，以及非默认热图形状按真实宽高回映射。未运行真实模型或视频，也未产生正式效果结论。

SHA256：

- `run.py`: `315a714129783d55cd246378b7f599cc57f0068f66f736d0db71d36626eebbbc`
- `test_run.py`: `170fec04422fcfb8c61ef6b264911224a22b512fc0b027476fa3da362c713e45`
- 源 `modules/models/tracknet/predictor.py`: `d8208470e973ff4388d8c34be54f19609a50a61571e72aaa3ed45dcaf8c34152`

## 实际结果与收口

主控已串行完成三种尺寸的完整 A-short 识别；本轮只读取结果并生成报告，没有重新运行模型或视频。三组均由 MPS 完成 4,200 帧并到达 EOF，各 1,400 次三帧调用。288×512 原始预测与 OPT-07A 已保存候选逐项一致；两种缩小尺寸本轮不采用，不补 C-short，不改产品代码。

正式报告位于 apps/video-clipper/reports/opt08a-size/README.md 和 summary.json。按区间并集计算，216×384 相对控制缺失 80 ms、额外保留 6,760 ms；144×256 缺失 880 ms、额外保留 2,040 ms。两种候选的 4,200 个输出球点均至少一个数值字段不同。无匹配人工标签，报告只把它们称为输出变化，未作准确率或真值漏失判断；单次耗时也未作稳定性能结论。

复核 JSON 与截图已逐字节复制到正式报告目录，SHA256 分别为 c03b53b7c63b1eec9c6f3c8d619ce42badff0c17605b915e9e0fd22a26bac5eb 和 987a58441030abb99df4fd3ccf007f9f854bbe60f94180b5a59fba77e7892dec。查看器实际播放 8→17 秒；截图保存 13.022 秒这一时点，用于定位新增保留风险。未逐帧审核或人工标注。

收口检查：汇总脚本读取三份运行 JSON、验证 EOF 与调用数、验证 288×512 与 OPT-07A 对照相等，并计算逐段缺失/新增、球点数值差、采样资源与运行哈希；脚本完成执行。py_compile 与 git diff --check 通过。三组 opencv_threads 记录为 18，按实际记录写入汇总。任务状态建议更新为“本轮实验完成、两候选不采用、待独立验收”。

收口文件 SHA256：

- summarize.py: 1bdf67043dfce85372784268c7790d9462f88d9b701c41b234c6420f540cab96
- apps/video-clipper/reports/opt08a-size/summary.json: 517003e610fb8eda0b39152776356e78863e05304bf41c901f80e82ad3f484d1
- apps/video-clipper/reports/opt08a-size/README.md: 513f95dc782127569afceb98c3c097d8abc451d881b2bbecf562f5505165336a
