# -*- coding: utf-8 -*-
"""版式报告的「文档块」模型。

报告内容先拼成一串与渲染器无关的块（标题 / 段落 / 表格 / 图片 / 分页），
再由 render_docx（python-docx）与 render_pdf（reportlab）各渲染一遍。
两份产物内容完全一致，只是引擎不同——这样 Word 与 PDF 不会出现"两套内容对不上"。

块的统一形状是 (kind, payload)：

=============  ==========================================================
kind           payload
=============  ==========================================================
h1 ... h4      字符串（标题文字，级别越小越靠上）
p              字符串（正文段落，可用 \n 分成多段）
bullets        字符串列表（带序号的条目，序号在内容里就已排好）
table          字典：headers / rows / widths / align / spans / zebra
img            字典：data（PNG 字节）/ width_cm / caption
pagebreak      None
spacer         数字（磅值）
note           字符串（小字说明，灰色）
=============  ==========================================================
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------- 工厂函数
def h1(text: str):
    return ("h1", text)


def h2(text: str):
    return ("h2", text)


def h3(text: str):
    return ("h3", text)


def h4(text: str):
    return ("h4", text)


def p(text: str):
    return ("p", text)


def bullets(items):
    return ("bullets", list(items))


def note(text: str):
    return ("note", text)


def pagebreak():
    return ("pagebreak", None)


def spacer(points: float = 8):
    return ("spacer", points)


def img(data: bytes, width_cm: float = 16.0, caption: str = ""):
    return ("img", {"data": data, "width_cm": width_cm, "caption": caption})


def table(headers, rows, widths=None, align=None, spans=None, zebra=False):
    """表格块。

    :param headers: 表头文字列表（传空列表则渲染成无表头的表）
    :param rows:    数据行，二维列表；单元格可以是字符串或数字
    :param widths:  各列相对宽度（同一套比例同时给 Word 与 PDF 用）
    :param align:   各列对齐，取值 l / c / r
    :param spans:   合并单元格，(r1, c1, r2, c2) 闭区间、0 基、行号不计表头
    :param zebra:   是否隔行浅底纹
    """
    return ("table", {"headers": list(headers or []),
                      "rows": [[("" if v is None else v) for v in row] for row in rows],
                      "widths": list(widths or []),
                      "align": list(align or []),
                      "spans": list(spans or []),
                      "zebra": bool(zebra)})


class Report:
    """一份版式报告：标题 + 元信息 + 块序列。"""

    def __init__(self, title: str, meta: dict, blocks: list):
        self.title = title
        self.meta = dict(meta or {})
        self.blocks = list(blocks or [])

    # -------------------------------------------------------- 统计（写进导出归档）
    def stats(self) -> dict:
        counts: dict = {}
        images = 0
        tables = 0
        for kind, _payload in self.blocks:
            counts[kind] = counts.get(kind, 0) + 1
            if kind == "img":
                images += 1
            elif kind == "table":
                tables += 1
        return {"blocks": len(self.blocks), "tables": tables, "images": images,
                "counts": counts}

    def device_count(self) -> int:
        return int(self.meta.get("device_count") or 0)

    def __repr__(self) -> str:                                  # pragma: no cover
        return "<Report %s blocks=%d>" % (self.title, len(self.blocks))


def text_of(payload: Any) -> str:
    return "" if payload is None else str(payload)
