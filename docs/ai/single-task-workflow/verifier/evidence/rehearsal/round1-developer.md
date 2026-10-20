# 第一轮开发结果

已完成区间整理实现和 README 更新，未提交、合入或推送。

## 改动

- `ranges.py` 使用排序副本处理输入；相接区间与重叠区间合并；遇到 `start > end` 抛出 `ValueError`。
- `README.md` 说明输入输出、合并规则、输入不变性和错误行为，并提供运行示例及验证命令。
- `test_ranges.py` 增加输入不变、相接/重复/零长度区间及反向区间错误的覆盖。

## 验证

- `python3 -m unittest -v`：5 项通过。
- `git diff --check`：通过。
- 已检查本轮差异；仅包含 `ranges.py`、`README.md`、`test_ranges.py`。原有 `docs/plan/roadmap.md` 修改和 `docs/ai/` 未跟踪内容未改动。

## 假设与阻塞

- 按需求所述，输入项是由整数端点组成的二元组；未扩展对其他输入类型的校验。
- 无阻塞。独立验收尚未执行。
