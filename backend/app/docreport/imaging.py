# -*- coding: utf-8 -*-
"""把「命令回显」和「统计数字」画成图片。

两块能力：

1. **terminal_png**：把一条命令的原始回显渲染成终端风格截图（深色窗口 + 交通灯 + 等宽字）。
   报告里"每个命令的输出截图"就是它——数据来自平台留档的真实回显，不是现场补拍。
   中英文混排按显示宽度对齐（中文算两格），不会串行。
2. **bar_chart / donut_chart / line_chart**：纯 Pillow 手绘的图表，不引 matplotlib
   （服务器上少一个编译依赖），配色与本平台页面同一套（主色 #1A73E8）。

所有函数都返回 PNG 字节，直接喂给 Word / PDF 渲染器，不落临时文件。
"""
from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw

from . import fonts

# ---------------------------------------------------------------- 配色
BRAND = (26, 115, 232)
BRAND_SOFT = (66, 133, 244)
GREEN = (22, 163, 74)
ORANGE = (245, 158, 11)
RED = (220, 38, 38)
GRAY = (148, 163, 184)
INK = (32, 33, 36)
SUB = (95, 99, 104)
LINE = (226, 232, 240)
PANEL = (247, 249, 252)

TERM_HEAD = (30, 41, 59)
TERM_BG = (11, 18, 32)
TERM_TEXT = (230, 237, 243)
TERM_DIM = (148, 163, 184)
TERM_PROMPT = (126, 231, 135)


# ---------------------------------------------------------------- 文字工具
def _disp_len(text: str) -> int:
    """按"终端列数"算长度：中日韩全角字符算 2 列。"""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def _wrap(text: str, columns: int) -> list:
    """按显示列数折行（不打断单词更美观，但中文按字符断）。"""
    out = []
    for raw in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip()
        if not line:
            out.append("")
            continue
        while _disp_len(line) > columns:
            width = 0
            cut = 0
            for idx, ch in enumerate(line):
                width += 2 if ord(ch) > 0x2E80 else 1
                cut = idx + 1
                if width >= columns:
                    break
            out.append(line[:cut])
            line = line[cut:]
        out.append(line)
    return out


def _runs(text: str):
    """把一行切成 纯 ASCII / 非 ASCII 的连续片段，便于混排两种字体。"""
    if not text:
        return []
    segments = []
    current = text[0]
    ascii_now = ord(text[0]) <= 0x2E80
    for ch in text[1:]:
        is_ascii = ord(ch) <= 0x2E80
        if is_ascii == ascii_now:
            current += ch
        else:
            segments.append((current, ascii_now))
            current, ascii_now = ch, is_ascii
    segments.append((current, ascii_now))
    return segments


def _draw_mixed(draw, x, y, text, ascii_font, cjk_font, fill):
    """画一行中英混排文字，返回结束时的 x。"""
    for segment, is_ascii in _runs(text):
        font = ascii_font if is_ascii else cjk_font
        draw.text((x, y), segment, font=font, fill=fill)
        x += draw.textlength(segment, font=font)
    return x


# ---------------------------------------------------------------- 终端截图
def terminal_png(title: str, command: str, output: str, *, prompt: str = "<HUAWEI>",
                 font_size: int = 13, scale: int = 2, max_columns: int = 104,
                 max_lines: int = 58, min_columns: int = 46) -> bytes:
    """把一条命令的回显渲染成终端风格截图，返回 PNG 字节。

    :param title:    标题栏文字（通常就是命令本身）
    :param command:  正文里回显的提示符行，例如 "display version"
    :param output:   命令的原始回显（平台留档的裁剪版本）
    :param max_lines: 超过就截断并注明（截图只作视觉凭证，完整回显在采集日志里）
    """
    size = max(9, int(font_size)) * scale
    body_font = fonts.pillow_font(size, mono=True)
    cjk_font = fonts.pillow_font(size)
    head_font = fonts.pillow_font(size, bold=True)

    lines = []
    if command:
        lines.append(_wrap((prompt + " " + command).strip(), max_columns)[0]
                     if _disp_len((prompt + " " + command).strip()) > max_columns
                     else (prompt + " " + command).strip())
    body = _wrap(output or "", max_columns)
    truncated = False
    if len(body) > max_lines:
        body = body[:max_lines]
        truncated = True
    lines.extend(body)
    if not body:
        lines.append("（该命令本次没有回显内容）")
    if truncated:
        lines.append("… 回显过长，此处截断；完整内容见平台「采集日志 → 看回显」")

    columns = max((_disp_len(x) for x in lines), default=0)
    columns = max(min_columns, min(max_columns, columns))

    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    char_w = max(1, int(round(probe.textlength("0", font=body_font))))
    line_h = int(round(size * 1.55))
    pad = int(round(size * 0.85))
    header_h = int(round(size * 2.1))

    width = pad * 2 + columns * char_w
    height = header_h + pad + len(lines) * line_h + pad
    image = Image.new("RGB", (width, height), TERM_BG)
    draw = ImageDraw.Draw(image)

    # 标题栏：三个交通灯 + 命令名
    draw.rectangle([0, 0, width, header_h], fill=TERM_HEAD)
    for index, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = pad + int(size * 0.45) + index * int(size * 1.15)
        cy = header_h // 2
        radius = int(size * 0.38)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=color)
    draw.text((pad + int(size * 4.4), header_h // 2 - int(size * 0.62)),
              title or command or "命令回显", font=head_font, fill=TERM_DIM)

    y = header_h + pad
    for index, line in enumerate(lines):
        color = TERM_PROMPT if (index == 0 and command) else TERM_TEXT
        if index and line.startswith("… "):
            color = TERM_DIM
        _draw_mixed(draw, pad, y, line, body_font, cjk_font, color)
        y += line_h

    # 终端截图配色很有限（底色 + 文字 + 高亮），量化成调色板 PNG 能把体积砍掉一大截，
    # 报告里几十张截图叠加起来差别很明显（docx / pdf 的生成与打开都更快）
    palette = image.convert("P", palette=Image.ADAPTIVE, colors=16)
    buffer = io.BytesIO()
    palette.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


# ---------------------------------------------------------------- 图表
def _canvas(width: int, height: int, title: str):
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    if title:
        draw.text((28, 18), title, font=fonts.pillow_font(20, bold=True), fill=INK)
        draw.line([(28, 52), (width - 28, 52)], fill=LINE, width=2)
    return image, draw


def _save(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _nice_max(value: float) -> float:
    """给纵轴挑一个"好看"的上限（1 / 1.5 / 2 / 2.5 / 3 / 4 / 5 / 7.5 / 10 的倍数）。"""
    if value <= 0:
        return 1.0
    raw = value / 4.0                                # 纵轴固定 4 格
    magnitude = 10 ** math.floor(math.log10(raw))
    for step in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if raw <= step * magnitude:
            return float(4 * step * magnitude)
    return float(40 * magnitude)


def _level_color(value, warn, danger):
    if value is None:
        return GRAY
    if danger is not None and value >= danger:
        return RED
    if warn is not None and value >= warn:
        return ORANGE
    return GREEN


def score_color(value, warn: float = 75.0, danger: float = 60.0):
    """健康分这类"越高越好"的指标配色（与百分比阈值的方向相反）。"""
    if value is None:
        return GRAY
    if value < danger:
        return RED
    if value < warn:
        return ORANGE
    return GREEN


def bar_chart(title: str, labels, values, *, unit: str = "%", warn=None, danger=None,
              threshold: float | None = None, threshold_label: str = "",
              width: int = 1180, height: int = 400, show_value: bool = True,
              colors=None, y_max: float | None = None) -> bytes:
    """纵向柱状图：按阈值上色（绿 / 橙 / 红），可选一条虚线阈值。

    colors 可以逐根柱子指定颜色（健康度这种"越高越好"的指标用它）；
    y_max 用于固定纵轴上限（例如健康度固定 0-100）。
    """
    labels = list(labels or [])
    values = list(values or [])
    image, draw = _canvas(width, height, title)
    if not labels:
        draw.text((28, 120), "（暂无可绘制的数据）", font=fonts.pillow_font(18), fill=SUB)
        return _save(image)

    left, right, top, bottom = 74, 34, 84, 78
    plot_w = width - left - right
    plot_h = height - top - bottom
    numeric = [v for v in values if isinstance(v, (int, float))]
    if not numeric:
        draw.text((28, 130), "（该指标本设备未采集到数据）",
                  font=fonts.pillow_font(18), fill=SUB)
        return _save(image)
    if y_max is None:
        y_max = _nice_max(max(numeric + [threshold or 0.0, 1.0]) * 1.15 if numeric else 1.0)

    # 横向网格 + y 轴刻度
    for tick in range(5):
        value = y_max * tick / 4.0
        y = top + plot_h - plot_h * tick / 4.0
        draw.line([(left, y), (left + plot_w, y)], fill=LINE, width=1)
        text = "%.0f" % value if unit != "%" or True else "%.1f" % value
        draw.text((left - 46, y - 9), text + unit, font=fonts.pillow_font(13), fill=SUB)

    slot = plot_w / float(len(labels))
    bar_w = max(14, min(78, int(slot * 0.55)))
    label_font = fonts.pillow_font(13)
    for index, label in enumerate(labels):
        value = values[index] if index < len(values) else None
        cx = left + slot * index + slot / 2.0
        if isinstance(value, (int, float)):
            bar_h = max(2, int(plot_h * min(1.0, value / y_max)))
            color = (colors[index] if colors and index < len(colors)
                     else _level_color(value, warn, danger))
            x1, y1 = cx - bar_w / 2.0, top + plot_h - bar_h
            x2, y2 = cx + bar_w / 2.0, top + plot_h
            draw.rectangle([x1, y1, x2, y2], fill=color)
            draw.rectangle([x1, y1, x2, y2], outline=color)
            if show_value:
                text = ("%.0f" % value) + (unit if unit == "%" else "")
                tw = draw.textlength(text, font=label_font)
                draw.text((cx - tw / 2, y1 - 20), text, font=label_font, fill=INK)
        else:
            tw = draw.textlength("未采集", font=label_font)
            draw.text((cx - tw / 2, top + plot_h - 18), "未采集", font=label_font, fill=GRAY)
        # x 轴标签（过长截断）
        text = str(label)
        if _disp_len(text) > 11:
            text = text[:9] + "…"
        tw = draw.textlength(text, font=label_font)
        draw.text((cx - tw / 2, top + plot_h + 12), text, font=label_font, fill=SUB)

    draw.line([(left, top + plot_h), (left + plot_w, top + plot_h)], fill=SUB, width=2)

    if threshold is not None and y_max > 0:
        y = top + plot_h - plot_h * min(1.0, threshold / y_max)
        x = left
        while x < left + plot_w:
            draw.line([(x, y), (min(x + 14, left + plot_w), y)], fill=RED, width=3)
            x += 24
        if threshold_label:
            tw = draw.textlength(threshold_label, font=fonts.pillow_font(13))
            draw.text((left + plot_w - tw - 4, y - 22), threshold_label,
                      font=fonts.pillow_font(13), fill=RED)
    return _save(image)


def donut_chart(title: str, parts, *, width: int = 1000, height: int = 360,
                center_label: str = "", unit: str = "台") -> bytes:
    """环形占比图：parts = [(名称, 数值, 颜色), ...]。"""
    parts = [(str(n), v, c) for n, v, c in (parts or []) if v]
    image, draw = _canvas(width, height, title)
    total = sum(v for _n, v, _c in parts)
    if not total:
        draw.text((28, 120), "（暂无可绘制的数据）", font=fonts.pillow_font(18), fill=SUB)
        return _save(image)

    size = min(height - 130, 210)
    box = [100, 92, 100 + size * 2, 92 + size * 2]
    start = -90.0
    for _name, value, color in parts:
        extent = 360.0 * value / total
        draw.pieslice(box, start=start, end=start + extent - 0.6, fill=color)
        start += extent
    inner = [box[0] + size * 0.62, box[1] + size * 0.62,
             box[2] - size * 0.62, box[3] - size * 0.62]
    draw.ellipse(inner, fill=(255, 255, 255))
    text = str(total)
    tw = draw.textlength(text, font=fonts.pillow_font(30, bold=True))
    draw.text(((inner[0] + inner[2]) / 2 - tw / 2, (inner[1] + inner[3]) / 2 - 22),
              text, font=fonts.pillow_font(30, bold=True), fill=INK)
    sub = center_label or "合计"
    tw = draw.textlength(sub, font=fonts.pillow_font(14))
    draw.text(((inner[0] + inner[2]) / 2 - tw / 2, (inner[1] + inner[3]) / 2 + 16),
              sub, font=fonts.pillow_font(14), fill=SUB)

    legend_x = box[2] + 70
    legend_y = 108
    for name, value, color in parts:
        draw.rectangle([legend_x, legend_y, legend_x + 16, legend_y + 16], fill=color)
        label = "%s：%d %s（%.0f%%）" % (name, value, unit, 100.0 * value / total)
        draw.text((legend_x + 26, legend_y - 2), label, font=fonts.pillow_font(15), fill=INK)
        legend_y += 34
    return _save(image)


def line_chart(title: str, labels, series, *, unit: str = "%", width: int = 1180,
               height: int = 400, y_max: float | None = None) -> bytes:
    """折线图：series = [(名称, 数值列表, 颜色), ...]，用于看指标的走势。"""
    labels = list(labels or [])
    series = [(str(n), list(v or []), c) for n, v, c in (series or [])]
    image, draw = _canvas(width, height, title)
    if not labels or not series:
        draw.text((28, 120), "（暂无可绘制的数据）", font=fonts.pillow_font(18), fill=SUB)
        return _save(image)

    left, right, top, bottom = 74, 34, 84, 74
    plot_w = width - left - right
    plot_h = height - top - bottom
    flat = [v for _n, values, _c in series for v in values if isinstance(v, (int, float))]
    y_max = y_max or _nice_max(max(flat + [1]) * 1.2)

    for tick in range(5):
        y = top + plot_h - plot_h * tick / 4.0
        draw.line([(left, y), (left + plot_w, y)], fill=LINE, width=1)
        draw.text((left - 46, y - 9), ("%.0f" % (y_max * tick / 4.0)) + unit,
                  font=fonts.pillow_font(13), fill=SUB)

    count = len(labels)
    def px(index):
        return left + (plot_w * index / max(1, count - 1)) if count > 1 else left + plot_w / 2

    for name, values, color in series:
        points = [(px(i), top + plot_h - plot_h * min(1.0, (v / y_max)))
                  for i, v in enumerate(values) if isinstance(v, (int, float))]
        if len(points) > 1:
            draw.line(points, fill=color, width=3, joint="curve")
        for x, y in points:
            draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=color)

    draw.line([(left, top + plot_h), (left + plot_w, top + plot_h)], fill=SUB, width=2)
    step = max(1, (count + 4) // 5)                 # 最多画 6 个刻度，避免叠字
    label_font = fonts.pillow_font(12)
    shown = set(range(0, count, step))
    shown.add(count - 1)
    for index in sorted(shown):
        if index and index < count - 1 and (count - 1 - index) < step * 0.6:
            continue                                # 与右端最后一个刻度太近就不画
        text = str(labels[index])
        tw = draw.textlength(text, font=label_font)
        draw.text((px(index) - tw / 2, top + plot_h + 12), text, font=label_font, fill=SUB)

    legend_y = top - 26
    legend_x = left
    for name, _values, color in series:
        draw.line([(legend_x, legend_y), (legend_x + 26, legend_y)], fill=color, width=4)
        draw.text((legend_x + 32, legend_y - 10), name, font=fonts.pillow_font(14), fill=INK)
        legend_x += 40 + int(draw.textlength(name, font=fonts.pillow_font(14))) + 24
    return _save(image)


def util_bars(title: str, rows, *, width: int = 1080, height: int | None = None) -> bytes:
    """横向占用率条：rows = [(标签, 数值或 None, 说明), ...]，用于资源利用率一览。"""
    rows = list(rows or [])
    row_h = 58
    height = height or (96 + row_h * max(1, len(rows)))
    image, draw = _canvas(width, height, title)
    if not rows:
        draw.text((28, 120), "（暂无可绘制的数据）", font=fonts.pillow_font(18), fill=SUB)
        return _save(image)
    left, right = 190, 150
    bar_w = width - left - right
    y = 84
    for label, value, hint in rows:
        draw.text((28, y + 6), str(label), font=fonts.pillow_font(16), fill=INK)
        draw.rectangle([left, y + 6, left + bar_w, y + 30], fill=(238, 242, 247))
        if isinstance(value, (int, float)):
            filled = max(3, int(bar_w * min(1.0, max(0.0, value) / 100.0)))
            color = _level_color(value, 80, 90)
            draw.rectangle([left, y + 6, left + filled, y + 30], fill=color)
            text = "%.0f%%" % value
        else:
            color = GRAY
            text = "未采集"
        draw.text((left + bar_w + 16, y + 6), text, font=fonts.pillow_font(16, bold=True),
                  fill=color)
        if hint:
            draw.text((left, y + 34), str(hint), font=fonts.pillow_font(12), fill=SUB)
        y += row_h
    return _save(image)
