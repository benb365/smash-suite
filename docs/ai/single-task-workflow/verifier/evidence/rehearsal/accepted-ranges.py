def compact_ranges(ranges):
    ordered = sorted(ranges)
    merged = []
    for start, end in ordered:
        if start > end:
            raise ValueError("range start must not exceed range end")
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
