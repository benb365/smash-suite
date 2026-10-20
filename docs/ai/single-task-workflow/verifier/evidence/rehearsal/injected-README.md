# 区间整理

`compact_ranges(ranges)` 接收由非负整数端点组成的 `(start, end)` 区间列表，返回按开始位置排序的元组列表。重叠区间会合并，首尾相接会保留为两段，零长度区间会保留；输入列表及其元素不会被修改。若任一区间的开始位置大于结束位置，函数会抛出 `ValueError`。

示例：

```python
from ranges import compact_ranges

compact_ranges([(3, 5), (0, 2), (2, 4)])  # [(0, 5)]
```

运行验证：`python3 -m unittest -v`。
