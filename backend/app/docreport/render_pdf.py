# -*- coding: utf-8 -*-
"""把文档块渲染成 PDF（.pdf）——reportlab platypus。

与 render_docx 用同一份块序列，因此 Word 与 PDF 的内容、表格、图片完全一致。
页脚自动写 "第 X 页 / 共 Y 页"（用 NumberedCanvas 两遍扫描拿到总页数），
封面与副封面不编页码，正文从第 1 页起。
"""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, Image,
                                KeepTogether, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

from . import fonts

HEAD_FILL = colors.HexColor("#1A73E8")
ZEBRA_FILL = colors.HexColor("#F7F9FC")
GRID_COLOR = colors.HexColor("#B7C0CE")
RULE_COLOR = colors.HexColor("#1A73E8")
SUB_COLOR = colors.HexColor("#5F6368")
INK = colors.HexColor("#202124")
TITLE_COLOR = colors.HexColor("#142A50")

MARGIN_X, MARGIN_Y = 2.54 * cm, 2.4 * cm
CONTENT_W = A4[0] - MARGIN_X * 2
CONTENT_H = A4[1] - MARGIN_Y * 2
MAX_IMAGE_H = 19.0 * cm

ALIGN = {"l": TA_LEFT, "c": TA_CENTER, "r": TA_RIGHT}


def _esc(value) -> str:
    return escape("" if value is None else str(value)).replace("\n", "<br/>")


def _styles():
    regular, bold = fonts.reportlab_fonts()
    common = {"wordWrap": "CJK"}
    return {
        "h1": ParagraphStyle("h1", fontName=bold, fontSize=15, leading=23,
                             spaceBefore=16, spaceAfter=8, textColor=TITLE_COLOR),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=13, leading=20,
                             spaceBefore=13, spaceAfter=6, textColor=TITLE_COLOR),
        "h3": ParagraphStyle("h3", fontName=bold, fontSize=12, leading=18,
                             spaceBefore=10, spaceAfter=5, textColor=TITLE_COLOR),
        "h4": ParagraphStyle("h4", fontName=bold, fontSize=11, leading=17,
                             spaceBefore=8, spaceAfter=4, textColor=TITLE_COLOR),
        "p": ParagraphStyle("p", fontName=regular, fontSize=10.5, leading=17,
                            spaceAfter=6, textColor=INK, **common),
        "note": ParagraphStyle("note", fontName=regular, fontSize=9, leading=14,
                               spaceAfter=4, textColor=SUB_COLOR, **common),
        "caption": ParagraphStyle("caption", fontName=regular, fontSize=9, leading=14,
                                  spaceBefore=2, spaceAfter=10, alignment=TA_CENTER,
                                  textColor=SUB_COLOR, **common),
        "cell": ParagraphStyle("cell", fontName=regular, fontSize=9, leading=13.5,
                               textColor=INK, **common),
        "cellc": ParagraphStyle("cellc", fontName=regular, fontSize=9, leading=13.5,
                                alignment=TA_CENTER, textColor=INK, **common),
        "cellr": ParagraphStyle("cellr", fontName=regular, fontSize=9, leading=13.5,
                                alignment=TA_RIGHT, textColor=INK, **common),
        "head": ParagraphStyle("head", fontName=bold, fontSize=9.5, leading=14,
                               alignment=TA_CENTER, textColor=colors.white, **common),
        "cover_title": ParagraphStyle("cover_title", fontName=bold, fontSize=24,
                                      leading=38, alignment=TA_CENTER,
                                      textColor=TITLE_COLOR, **common),
        "cover_project": ParagraphStyle("cover_project", fontName=bold, fontSize=16,
                                        leading=30, textColor=TITLE_COLOR, **common),
        "cover_sub": ParagraphStyle("cover_sub", fontName=bold, fontSize=14,
                                    leading=30, textColor=TITLE_COLOR, **common),
        "cover_line": ParagraphStyle("cover_line", fontName=regular, fontSize=12,
                                     leading=30, **common),
        "cover_right": ParagraphStyle("cover_right", fontName=regular, fontSize=12,
                                      leading=34, alignment=TA_RIGHT, **common),
        "cover_center": ParagraphStyle("cover_center", fontName=regular, fontSize=13,
                                       leading=28, alignment=TA_CENTER, **common),
    }


# ---------------------------------------------------------------- 页脚 / 总页数
class NumberedCanvas(pdfcanvas.Canvas):
    """两遍扫描拿总页数：封面与副封面不编页码，正文写 "第 X 页 / 共 Y 页"。"""

    def __init__(self, *args, meta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._meta = meta or {}
        self._states = []
        self._regular = fonts.reportlab_fonts()[0]
        self._cover_pages = 2 if self._meta.get("cover") else 0

    def showPage(self):                                     # noqa: N802
        self._states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = max(0, len(self._states) - self._cover_pages)
        for index, state in enumerate(self._states):
            self.__dict__.update(state)
            if index >= self._cover_pages:                  # 封面 / 副封面不编页码
                self._footer(index - self._cover_pages + 1, total)
            super().showPage()
        super().save()

    def _footer(self, page: int, total: int):
        self.saveState()
        self.setFont(self._regular, 9)
        self.setFillColor(SUB_COLOR)
        self.drawCentredString(A4[0] / 2.0, 1.45 * cm,
                               "第 %d 页 / 共 %d 页" % (page, total))
        label = self._meta.get("footer") or ""
        if label:
            self.drawRightString(A4[0] - MARGIN_X, 1.45 * cm, label)
        self.restoreState()


# ---------------------------------------------------------------- 表格
def _table(block, styles):
    headers = block["headers"]
    rows = block["rows"]
    widths = block["widths"] or [1] * max([len(headers)] + [len(r) for r in rows] or [1])
    columns = max([len(headers)] + [len(r) for r in rows] or [1])
    if len(widths) < columns:
        widths = list(widths) + [1] * (columns - len(widths))
    total = float(sum(widths[:columns])) or 1.0
    col_w = [CONTENT_W * w / total for w in widths[:columns]]
    aligns = block["align"] or []

    data = []
    if headers:
        data.append([Paragraph(_esc(headers[i] if i < len(headers) else ""), styles["head"])
                     for i in range(columns)])
    for row in rows:
        cells = []
        for i in range(columns):
            align = aligns[i] if i < len(aligns) else "l"
            style = styles["cellc" if align == "c" else "cellr" if align == "r" else "cell"]
            cells.append(Paragraph(_esc(row[i] if i < len(row) else ""), style))
        data.append(cells)

    table = Table(data, colWidths=col_w, repeatRows=1 if headers else 0, hAlign="CENTER")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.5, GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if headers:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_FILL))
    if block["zebra"]:
        offset = 1 if headers else 0
        for index in range(len(rows)):
            if index % 2:
                commands.append(("BACKGROUND", (0, index + offset), (-1, index + offset),
                                 ZEBRA_FILL))
    for span in block["spans"]:
        r1, c1, r2, c2 = span
        offset = 1 if headers else 0
        if r2 + offset < len(data):
            commands.append(("SPAN", (c1, r1 + offset), (c2, r2 + offset)))
            commands.append(("VALIGN", (c1, r1 + offset), (c2, r2 + offset), "MIDDLE"))
    table.setStyle(TableStyle(commands))
    return table


def _image(payload, styles):
    image = Image(io.BytesIO(payload["data"]))
    natural_w, natural_h = image.imageWidth, image.imageHeight
    want = min(float(payload.get("width_cm") or 0) * cm or CONTENT_W, CONTENT_W)
    scale = want / float(natural_w or 1)
    if natural_h * scale > MAX_IMAGE_H:
        scale = MAX_IMAGE_H / float(natural_h or 1)
    image.drawWidth = natural_w * scale
    image.drawHeight = natural_h * scale
    image.hAlign = "CENTER"
    parts = [Spacer(1, 6), image]
    if payload.get("caption"):
        parts.append(Paragraph(_esc(payload["caption"]), styles["caption"]))
    else:
        parts.append(Spacer(1, 8))
    return KeepTogether(parts)


# ---------------------------------------------------------------- 封面 / 副封面
def _cover_flowables(meta, styles):
    cover = meta.get("cover") or {}
    flow = [Spacer(1, 112)]
    flow.append(Paragraph(_esc(cover.get("title") or ""), styles["cover_title"]))
    flow.append(Spacer(1, 10))
    flow.append(HRFlowable(width="58%", thickness=1.4, color=RULE_COLOR,
                           hAlign="CENTER", spaceAfter=0))
    flow.append(Spacer(1, 168))
    for line in cover.get("signatures") or []:
        flow.append(Paragraph(_esc(line), styles["cover_right"]))
    flow.append(Spacer(1, 150))
    flow.append(Paragraph(_esc(cover.get("org") or ""), styles["cover_center"]))
    flow.append(Paragraph(_esc(cover.get("date") or ""), styles["cover_center"]))
    return flow


def _subtitle_flowables(meta, styles):
    """副封面：项目名 + ——报告名 + 单位 + 日期（与现场样例同版式）。"""
    cover = meta.get("cover") or {}
    lines = cover.get("subtitle_page") or []
    flow = [Spacer(1, 150)]
    if lines:
        flow.append(Paragraph(_esc(lines[0]), styles["cover_project"]))
    if len(lines) > 1:
        flow.append(Paragraph(_esc(lines[1]), styles["cover_sub"]))
    flow.append(Spacer(1, 40))
    for line in lines[2:]:
        flow.append(Paragraph(_esc(line), styles["cover_line"]))
    return flow


# ---------------------------------------------------------------- 主入口
def render(report) -> bytes:
    """把 Report 渲染成 PDF 字节。"""
    styles = _styles()
    buffer = io.BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4,
                          leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                          topMargin=MARGIN_Y, bottomMargin=MARGIN_Y,
                          title=report.title,
                          author=(report.meta.get("org") or ""),
                          subject=(report.meta.get("subtitle") or ""),
                          creator=(report.meta.get("site") or "林鉴知微平台 | LinScopePlatform"))
    cover_frame = Frame(MARGIN_X, MARGIN_Y, CONTENT_W, CONTENT_H, id="cover")
    body_frame = Frame(MARGIN_X, MARGIN_Y, CONTENT_W, CONTENT_H, id="body")
    doc.addPageTemplates([PageTemplate(id="cover", frames=[cover_frame]),
                          PageTemplate(id="body", frames=[body_frame])])

    story = []
    if report.meta.get("cover"):
        story.extend(_cover_flowables(report.meta, styles))
        story.append(PageBreak())
        story.extend(_subtitle_flowables(report.meta, styles))
        story.append(NextPageTemplate("body"))
        story.append(PageBreak())

    for kind, payload in report.blocks:
        if kind == "pagebreak":
            story.append(PageBreak())
        elif kind == "spacer":
            story.append(Spacer(1, float(payload or 0)))
        elif kind in ("h1", "h2", "h3", "h4"):
            story.append(Paragraph(_esc(payload), styles[kind]))
        elif kind == "p":
            story.append(Paragraph(_esc(payload), styles["p"]))
        elif kind == "note":
            story.append(Paragraph(_esc(payload), styles["note"]))
        elif kind == "bullets":
            for item in payload:
                story.append(Paragraph(_esc(item), styles["p"]))
        elif kind == "table":
            story.append(Spacer(1, 2))
            story.append(_table(payload, styles))
            story.append(Spacer(1, 4))
        elif kind == "img":
            story.append(_image(payload, styles))

    doc.build(story, canvasmaker=lambda *a, **kw: NumberedCanvas(
        *a, meta=report.meta, **kw))
    return buffer.getvalue()

