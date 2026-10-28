# -*- coding: utf-8 -*-
"""报表接口：导出 Excel / CSV / Word / PDF，以及导出归档（报告中心）。"""
from __future__ import annotations

import hashlib
import json

import urllib.parse
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response

from .. import auth, config, docreport, report, service
from ..store import get_store

router = APIRouter(prefix="/api/reports", tags=["reports"])

KINDS_LABEL = {
    "overview": "巡检总览", "inspection": "巡检明细", "devices": "设备台账",
    "server": "服务器健康", "switch": "交换机健康", "security": "安全设备健康", "alerts": "告警处置",
    "backup": "配置备份", "audit": "操作审计", "ledger": "设备台账（含补充）",
}

KINDS = ("overview", "inspection", "devices", "server", "switch", "security", "alerts", "backup",
         "audit", "ledger")

#: 表格类格式（Excel / CSV）与版式类格式（Word / PDF）
TABLE_FORMATS = ("xlsx", "csv")
DOC_FORMATS = ("docx", "pdf")
FORMATS = TABLE_FORMATS + DOC_FORMATS

#: 版式报告支持的类型（与 app/docreport 保持一致）
DOC_KINDS = docreport.KINDS

MEDIA_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def _params(kind: str, hours: int, days: int, device: str,
            extra: dict | None = None) -> dict:
    params = {"kind": kind, "hours": hours, "days": days, "device": device}
    for key in ("customer", "project", "org"):
        value = (extra or {}).get(key)
        if value:
            params[key] = value
    return params


def _archive_file(export_id: int, filename: str, payload: bytes) -> tuple[str, str, int]:
    folder = config.DATA_DIR / "report-archive"
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename or "report.bin").name
    path = folder / ("%d-%s" % (export_id, safe_name))
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    get_store().attach_export_file(export_id, str(path), digest, len(payload))
    return str(path), digest, len(payload)


def _export_document(kind: str, fmt: str, params: dict, operator: str, archive: bool):
    """版式报告（Word / PDF）：一次生成整份报告，落一条归档记录。"""
    from fastapi.responses import Response as _Response
    import urllib.parse as _url

    filename, payload, stats = docreport.build(kind, params, fmt)
    rows = int(stats.get("devices") or 0)
    export_id = None
    if archive:
        export_id = get_store().add_export(kind, fmt, filename, rows, params, operator)
        _archive_file(export_id, filename, payload)
    quoted = _url.quote(filename)
    return _Response(content=payload, media_type=MEDIA_TYPES[fmt], headers={
        "Content-Disposition": "attachment; filename*=UTF-8''%s" % quoted,
        "X-Export-Id": str(export_id or ""),
        "X-Export-Rows": str(rows),
        "X-Export-Devices": str(rows),
        "X-Export-Tables": str(stats.get("tables") or 0),
        "X-Export-Images": str(stats.get("images") or 0),
        "X-Export-Source": service.status().get("source", ""),
        "Access-Control-Expose-Headers": "Content-Disposition, X-Export-Id, "
                                         "X-Export-Rows, X-Export-Devices, "
                                         "X-Export-Tables, X-Export-Images, "
                                         "X-Export-Source",
    })


@router.get("/templates")
def templates():
    return service.report_archive()["templates"]


def _filter_archive_device(rows: list, device: str, devices: list) -> list:
    """Match explicit single/multi-device exports by IP or stored device ID."""
    key = str(device or "").strip()
    if not key:
        return rows
    aliases = {key}
    for item in devices:
        if key in {str(item.get("id") or ""), str(item.get("ip") or "")}:
            aliases.update(str(item.get(field) or "") for field in ("id", "ip"))
    aliases.discard("")
    return [row for row in rows if aliases.intersection(
        part.strip() for part in str((row.get("params") or {}).get("device") or "").split(",")
    )]


@router.get("/archive")
def archive(keyword: str = "", kind: str = "", fmt: str = "",
            page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200), device: str = ""):
    """导出归档：支持关键字 / 类型 / 格式过滤与分页（实景里归档会很多）。"""
    data = service.report_archive()
    store = get_store()
    rows = []
    for item in data["exports"]:
        rows.append({
            "id": item["id"], "name": item.get("filename") or "",
            "kind": item.get("kind"), "format": item.get("fmt"),
            "kind_label": KINDS_LABEL.get(item.get("kind"), item.get("kind")),
            "rows": item.get("rows"), "operator": item.get("operator"),
            "created_at": item.get("created_at"),
            "params": item.get("params") or {},
        })
    if device.strip():
        rows = _filter_archive_device(rows, device, store.devices())
    kw = (keyword or "").strip().lower()
    if kw:
        rows = [r for r in rows
                if kw in (str(r["name"] or "") + " " + str(r["kind_label"] or "") + " " + str(r["operator"] or "")).lower()]
    if kind and kind != "all":
        rows = [r for r in rows if r["kind"] == kind]
    if fmt and fmt != "all":
        rows = [r for r in rows if r["format"] == fmt]
    page_size = max(1, page_size)
    total = len(rows)
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(1, page), pages)
    counts: dict = {}
    for item in data["exports"]:
        counts[item.get("kind")] = counts.get(item.get("kind"), 0) + 1
    return {"exports": rows[(page - 1) * page_size: page * page_size],
            "templates": data["templates"], "formats": data["formats"],
            "total": total, "page": page, "pages": pages, "page_size": page_size,
            "keyword": keyword, "kind": kind, "fmt": fmt, "device": device,
            "by_kind": [{"value": k, "label": KINDS_LABEL.get(k, k), "count": v}
                         for k, v in sorted(counts.items(), key=lambda kv: -kv[1])],
            "count": len(data["exports"]),
            "all_count": len(data["exports"]),
            "counts": store.counts()}


def _export_impl(kind: str = "overview", format: str = "xlsx",
                 hours: int = 24 * 30, days: int = 7,
                 device: str = "", customer: str = "", project: str = "", org: str = "",
                 operator: str = "admin", archive: bool = True):
    """导出报表：kind 选报表类型，format 选 xlsx / csv / docx / pdf。

    * xlsx / csv —— 全量数据表（任何 kind 都支持）；
    * docx / pdf —— 版式报告（封面 / 章节 / 逐条命令回显截图 / 数据分析 / 维护建议），
      只支持 server（服务器健康）与 switch（交换机健康）两类，见 app/docreport。
    """
    kind = (kind or "overview").lower()
    if kind not in KINDS:
        raise HTTPException(400, "kind 只能是 %s" % "、".join(KINDS))
    fmt = (format or "xlsx").lower()
    if fmt not in FORMATS:
        raise HTTPException(400, "format 只能是 %s" % " / ".join(FORMATS))
    params = _params(kind, hours, days, device,
                     {"customer": customer, "project": project, "org": org})
    if fmt in DOC_FORMATS:
        if kind not in DOC_KINDS:
            raise HTTPException(
                400, "Word / PDF 版式报告只支持 %s（服务器 / 交换机 / 安全设备）"
                     % " / ".join(DOC_KINDS))
        try:
            return _export_document(kind, fmt, params, operator, archive)
        except HTTPException:
            raise
        except Exception as exc:                        # noqa: BLE001
            raise HTTPException(500, "生成版式报告失败：%s" % exc)
    try:
        if fmt == "xlsx":
            filename, payload, rows = report.to_excel(kind, params)
        else:
            filename, payload, rows = report.to_csv(kind, params)
        media = MEDIA_TYPES[fmt]
    except HTTPException:
        raise
    except Exception as exc:                            # noqa: BLE001
        raise HTTPException(500, "生成报表失败：%s" % exc)

    export_id = None
    if archive:
        export_id = get_store().add_export(kind, fmt, filename, rows, params, operator)
        _archive_file(export_id, filename, payload)
    quoted = urllib.parse.quote(filename)
    return Response(content=payload, media_type=media, headers={
        "Content-Disposition": "attachment; filename*=UTF-8''%s" % quoted,
        "X-Export-Id": str(export_id or ""),
        "X-Export-Rows": str(rows),
        "X-Export-Source": service.status().get("source", ""),
        "Access-Control-Expose-Headers": "Content-Disposition, X-Export-Id, "
                                         "X-Export-Rows, X-Export-Source",
    })


@router.get("/export")
def export(request: Request, kind: str = Query("overview"), format: str = Query("xlsx"),
           hours: int = Query(24 * 30, ge=1, le=24 * 365),
           days: int = Query(7, ge=1, le=90),
           device: str = "", customer: str = "", project: str = "", org: str = "",
           archive: bool = True):
    user = request.state.user
    return _export_impl(kind=kind, format=format, hours=hours, days=days, device=device,
                        customer=customer, project=project, org=org,
                        operator=user["username"], archive=archive)


@router.get("/export/{export_id}")
def re_export(export_id: int, request: Request, format: str = ""):
    """优先下载归档时的原始文件；旧归档没有文件时才按参数重新生成。"""
    item = get_store().export(export_id)
    if not item:
        raise HTTPException(404, "导出记录不存在")
    archived = Path(item.get("file_path") or "")
    if archived.is_file() and archived.stat().st_size > 0:
        return FileResponse(
            archived,
            filename=item.get("filename") or archived.name,
            media_type=MEDIA_TYPES.get((format or item.get("fmt") or "xlsx").lower(),
                                       "application/octet-stream"))
    params = item.get("params") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception:
            params = {}
    user = request.state.user
    return _export_impl(kind=item.get("kind") or "overview",
                       format=(format or item.get("fmt") or "xlsx"),
                       hours=int(params.get("hours") or 24 * 30),
                       days=int(params.get("days") or 7),
                       device=params.get("device") or "",
                       customer=params.get("customer") or "",
                       project=params.get("project") or "",
                       operator=user["username"], archive=False)


@router.delete("/archive/{export_id}")
def delete_archive(export_id: int, request: Request):
    store = get_store()
    item = store.export(export_id)
    if not item:
        raise HTTPException(404, "导出记录不存在")
    archived = Path(item.get("file_path") or "")
    try:
        if archived.is_file():
            archived.unlink()
    except OSError:
        pass
    with store.connect() as conn:
        conn.execute("DELETE FROM exports WHERE id=?", (export_id,))
    user = request.state.user
    auth.log_event(user["username"], "archive_delete",
                   "删除报告归档 %s" % (item.get("filename") or export_id),
                   operator=user["username"], target_type="report")
    return {"ok": True, "deleted": export_id,
            "deleted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

