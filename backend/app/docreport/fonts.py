# -*- coding: utf-8 -*-
"""字体探测：不给报告"甩锅"到字体缺失上。

- Word（.docx）只写字体名（微软雅黑 / 宋体 / Consolas），由打开报告的 Word / WPS 解析，
  所以这边只需要给出一套通用的中文办公字体名；
- PDF（reportlab）与截图（Pillow）必须拿到**字体文件本体**，因此这里按候选列表探测
  Windows（微软雅黑 / 宋体 / 新宋体 / 黑体）与常见 Linux 发行版（Noto CJK / 文泉驿）的字体，
  一个都找不到时 PDF 回落到 reportlab 自带的 CID 字体 STSong-Light（一定可用，只是没有粗体）。
"""
from __future__ import annotations

import os
from functools import lru_cache

# (路径, ttc 内的子字体序号)；ttf 一律用 0
CJK_REGULAR = [
    ("C:/Windows/Fonts/msyh.ttc", 0),            # 微软雅黑
    ("C:/Windows/Fonts/simsun.ttc", 0),          # 宋体
    ("C:/Windows/Fonts/simhei.ttf", 0),          # 黑体
    ("C:/Windows/Fonts/Deng.ttf", 0),            # 等线
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
]

CJK_BOLD = [
    ("C:/Windows/Fonts/msyhbd.ttc", 0),          # 微软雅黑 Bold
    ("C:/Windows/Fonts/simhei.ttf", 0),          # 黑体
    ("C:/Windows/Fonts/Dengb.ttf", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
]

#: 等宽字体：终端回显截图用（优先新宋体——既有中文又是等宽，ASCII 对齐不失真）
MONO = [
    ("C:/Windows/Fonts/simsun.ttc", 1),          # NSimSun（新宋体）
    ("C:/Windows/Fonts/consola.ttf", 0),         # Consolas
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
    ("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansMono-Regular.ttf", 0),
]

#: 没有中文字体时 PDF 用的兜底 CID 字体（reportlab 内置，不需要字体文件）
CID_FALLBACK = "STSong-Light"

#: Word 文档里写的字体名（由 Word / WPS 解析，不需要本机存在）
WORD_BODY = ("Times New Roman", "宋体")
WORD_HEAD = ("Arial", "黑体")
WORD_TITLE = ("Arial", "微软雅黑")
WORD_MONO = "Consolas"


def _first(candidates):
    for path, index in candidates:
        try:
            if path and os.path.exists(path):
                return path, index
        except OSError:
            continue
    return None


@lru_cache(maxsize=8)
def cjk(mono: bool = False, bold: bool = False):
    """返回 (字体路径, ttc 子字体序号)；找不到返回 None。"""
    if mono:
        found = _first(MONO) or _first(CJK_REGULAR)
    elif bold:
        found = _first(CJK_BOLD) or _first(CJK_REGULAR)
    else:
        found = _first(CJK_REGULAR)
    return found


# ---------------------------------------------------------------- Pillow
@lru_cache(maxsize=64)
def pillow_font(size: int, bold: bool = False, mono: bool = False):
    """Pillow 字体对象（带缓存）；没有任何字体时返回 Pillow 默认位图字体。"""
    from PIL import ImageFont
    found = cjk(mono=mono, bold=bold)
    if found:
        path, index = found
        for kwargs in ({"index": index}, {}):
            try:
                return ImageFont.truetype(path, size, **kwargs)
            except Exception:                               # noqa: BLE001
                continue
    return ImageFont.load_default(size)


# ---------------------------------------------------------------- reportlab
_REGISTERED: dict = {}


def reportlab_fonts():
    """注册并返回 (正文字体名, 粗体名)。全部失败时返回内置 CID 字体名。"""
    if _REGISTERED.get("names"):
        return _REGISTERED["names"]
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular = bold = None
    for name, spec in (("DocCJK", cjk()), ("DocCJKBold", cjk(bold=True))):
        if not spec:
            continue
        path, index = spec
        try:
            if name in pdfmetrics.getRegisteredFontNames():
                pass
            else:
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=index))
            if name == "DocCJK":
                regular = name
            else:
                bold = name
        except Exception:                                   # noqa: BLE001
            continue
    if not regular:
        # 内置中文 CID 字体：一定有，只是没有粗体（用同一个字体模拟）
        try:
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            pdfmetrics.registerFont(UnicodeCIDFont(CID_FALLBACK))
            regular = CID_FALLBACK
        except Exception:                                   # noqa: BLE001
            regular = "Helvetica"
    names = (regular, bold or regular)
    _REGISTERED["names"] = names
    return names


def describe() -> dict:
    """探测结果（写进报告附录，排错时一眼看出用了哪套字体）。"""
    reg = cjk()
    bd = cjk(bold=True)
    mo = cjk(mono=True)
    return {
        "cjk": os.path.basename(reg[0]) if reg else ("reportlab:" + CID_FALLBACK),
        "cjk_bold": os.path.basename(bd[0]) if bd else "(same as cjk)",
        "mono": os.path.basename(mo[0]) if mo else "(default)",
        "pdf_fonts": reportlab_fonts()[0],
    }
