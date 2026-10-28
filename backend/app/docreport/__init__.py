# -*- coding: utf-8 -*-
"""版式报告（Word / PDF）：服务器 / 交换机健康性检查报告。

与本平台的 Excel / CSV 报表（app/report.py）并列、互不替代：

* Excel / CSV —— 给机器看的数据表（明细、汇总、可二次加工）；
* 本模块 —— 给人看的**版式报告**：封面、章节、评估标准表、现场巡检表、
  逐条命令的回显截图、数据分析图表、维护建议，一次导出 Word 与 PDF 两份。

两者的取数口径完全一致（都读同一套 service / store），不存在"两个报告对不上"的问题。
渲染链路：content 装配「文档块」→ render_docx（python-docx）/ render_pdf（reportlab）。

依赖：python-docx / reportlab / pillow（见 backend/requirements.txt）。
"""
from __future__ import annotations

from datetime import datetime

from . import content
from .blocks import Report
from .content import build as build_report

KINDS = content.KINDS
FORMATS = ("docx", "pdf")
LABELS = content.TITLES


def build(kind: str = "switch", params: dict | None = None, fmt: str = "docx"):
    """生成版式报告，返回 (文件名, 二进制内容, 统计信息)。

    统计信息会写进「巡检报告中心」的导出归档，形如
    {"devices": 6, "tables": 21, "images": 30, "blocks": 210}。
    """
    kind = (kind or "switch").lower()
    if kind not in KINDS:
        raise ValueError("版式报告只支持 %s" % "、".join(KINDS))
    fmt = (fmt or "docx").lower()
    if fmt not in FORMATS:
        raise ValueError("版式报告只支持 %s" % " / ".join(FORMATS))

    report = build_report(kind, params or {})
    if fmt == "docx":
        from . import render_docx
        payload = render_docx.render(report)
    else:
        from . import render_pdf
        payload = render_pdf.render(report)

    stats = report.stats()
    stats["devices"] = report.device_count()
    stats["period"] = report.meta.get("period") or ""
    stats["title"] = report.title
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = "%s-%s.%s" % (report.title, stamp, fmt)
    return filename, payload, stats


def to_docx(kind: str = "switch", params: dict | None = None):
    return build(kind, params, "docx")


def to_pdf(kind: str = "switch", params: dict | None = None):
    return build(kind, params, "pdf")


def title_of(kind: str) -> str:
    return LABELS.get((kind or "").lower(), "")


__all__ = ["build", "to_docx", "to_pdf", "title_of", "KINDS", "FORMATS", "Report"]

