"""Create a compact badminton court and per-shot arrows as an ASS overlay."""
from __future__ import annotations

import math
from pathlib import Path

from modules.trajectory.constraints import constrain_shots


COURT_WIDTH_M = 6.10
COURT_LENGTH_M = 13.40
SINGLES_LEFT_M = 0.0
SINGLES_RIGHT_M = 5.18


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        x, y = map(float, value)
    except (TypeError, ValueError):
        return None
    return (x, y) if math.isfinite(x) and math.isfinite(y) else None


def _stamp(milliseconds: float) -> str:
    centiseconds = max(0, round(milliseconds / 10))
    hours, centiseconds = divmod(centiseconds, 360_000)
    minutes, centiseconds = divmod(centiseconds, 6_000)
    seconds, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02}:{seconds:02}.{centiseconds:02}"


def _polygon(points) -> str:
    coords = " ".join(f"{command} {round(x)} {round(y)}" for command, x, y in points)
    return coords


def _rect(x0, y0, x1, y1) -> str:
    return _polygon([("m", x0, y0), ("l", x1, y0), ("l", x1, y1), ("l", x0, y1)])


def _line(x0, y0, x1, y1, thickness):
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length == 0:
        return ""
    nx, ny = -dy * thickness / (2 * length), dx * thickness / (2 * length)
    return _polygon([("m", x0 + nx, y0 + ny), ("l", x1 + nx, y1 + ny),
                     ("l", x1 - nx, y1 - ny), ("l", x0 - nx, y0 - ny)])


def _ass_draw(drawing: str, color: str, *, alpha: str = "00") -> str:
    return f"{{\\an7\\pos(0,0)\\1c&H{color}&\\1a&H{alpha}&\\bord0\\shad0\\p1}}{drawing}{{\\p0}}"


def _court_drawings(width: int, height: int):
    panel_height = max(1, round(height * .30))
    panel_width = max(1, round(panel_height * COURT_WIDTH_M / COURT_LENGTH_M))
    margin = max(2, round(min(width, height) * .012))
    left, top = width - panel_width - margin, margin
    right, bottom = left + panel_width, top + panel_height
    sx, sy = panel_width / COURT_WIDTH_M, panel_height / COURT_LENGTH_M
    line_width = max(1, panel_width * .018)

    def xy(x, y):
        return left + (x + .46) * sx, top + y * sy

    background = _ass_draw(_rect(left, top, right, bottom), "24231F", alpha="48")
    lines = []

    def segment(a, b):
        x0, y0 = xy(*a)
        x1, y1 = xy(*b)
        drawing = _line(x0, y0, x1, y1, line_width)
        if drawing:
            lines.append(drawing)

    # Doubles boundary, singles sidelines, service lines, center lines and net.
    for x in (-.46, 5.64, 0.0, 5.18):
        segment((x, 0), (x, COURT_LENGTH_M))
    for y in (0, .76, 4.72, 6.7, 8.68, 12.64, COURT_LENGTH_M):
        segment((-.46, y), (5.64, y))
    segment((2.59, 0), (2.59, 4.72))
    segment((2.59, 8.68), (2.59, COURT_LENGTH_M))
    return left, top, right, bottom, background, lines, xy, line_width


def _arrow(start, end, xy, thickness):
    x0, y0 = xy(*start)
    x1, y1 = xy(*end)
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1:
        return ""
    head = max(4, thickness * 4)
    ux, uy = dx / length, dy / length
    base_x, base_y = x1 - ux * head, y1 - uy * head
    half = head * .55
    perp_x, perp_y = -uy * half, ux * half
    shaft_end_x, shaft_end_y = x1 - ux * head * .8, y1 - uy * head * .8
    shaft = _line(x0, y0, shaft_end_x, shaft_end_y, thickness * 1.7)
    tip = _polygon([("m", x1, y1), ("l", base_x + perp_x, base_y + perp_y),
                    ("l", base_x - perp_x, base_y - perp_y)])
    return f"{shaft} {tip}"


def _output_intervals(start_ms: float, end_ms: float, export_ranges: list[list[float]]):
    prefix = 0.0
    for source_start, source_end in export_ranges:
        start, end = max(start_ms, source_start), min(end_ms, source_end)
        if end > start:
            yield prefix + start - source_start, prefix + end - source_start
        prefix += source_end - source_start


def write_overlay(paths: dict, export_ranges: list[list[float]], destination: Path, width: int, height: int):
    """Write an ASS overlay using source shot times and the export's kept ranges."""
    if not isinstance(paths, dict) or not isinstance(paths.get("shots"), list):
        raise ValueError("球路分析结果缺少逐拍轨迹。")
    _, _, _, _, background, lines, xy, thickness = _court_drawings(width, height)
    duration_ms = sum(end - start for start, end in export_ranges)
    if duration_ms <= 0:
        raise ValueError("球路叠图缺少有效的成片时间范围。")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    end = _stamp(duration_ms)
    event_lines = [f"Dialogue: 0,0:00:00.00,{end},Default,,0,0,0,,{background}"]
    for line in lines:
        event_lines.append(f"Dialogue: 0,0:00:00.00,{end},Default,,0,0,0,,{_ass_draw(line, 'FFFFFF')}")

    for shot in constrain_shots(paths["shots"]):
        if not isinstance(shot, dict) or shot.get("end_kind") == "unresolved":
            continue
        start, finish = shot.get("start_ms"), shot.get("end_ms")
        start_point, end_point = _point(shot.get("start_xy")), _point(shot.get("end_xy"))
        try:
            start, finish = float(start), float(finish)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(start) or not math.isfinite(finish) or finish <= start or not start_point or not end_point:
            continue
        drawing = _arrow(start_point, end_point, xy, thickness)
        if not drawing:
            continue
        text = _ass_draw(drawing, "00D7FF")
        for output_start, output_end in _output_intervals(start, finish, export_ranges):
            event_lines.append(f"Dialogue: 1,{_stamp(output_start)},{_stamp(output_end)},Default,,0,0,0,,{text}")

    destination.write_text(header + "\n".join(event_lines) + "\n", encoding="utf-8")
