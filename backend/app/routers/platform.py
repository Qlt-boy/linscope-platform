# -*- coding: utf-8 -*-
"""总览 / 设备 / 健康检查 / 告警 / 巡检 / 备份 接口。"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query, Request

from .. import auth, service
from ..store import get_store
from datetime import datetime

router = APIRouter(prefix="/api", tags=["platform"])


# ------------------------------------------------------------------ 总览
@router.get("/dashboard/overview")
def dashboard_overview(days: int = Query(7, ge=1, le=90)):
    return service.overview(days)


@router.get("/dashboard/wall")
def dashboard_wall():
    """大屏轮播：交换机 / 服务器两块，每台设备的核心采集指标。"""
    return service.wall_view()


@router.get("/dashboard/resources")
def dashboard_resources(days: int = Query(7, ge=1, le=90)):
    """CPU / 内存 曲线与逐设备使用率（仪表盘第二个图表用）。"""
    data = service.overview(days)
    return {"source": data["source"], "source_info": data["source_info"],
            "period": data["period"], "resources": data["resources"],
            "kpis": data["kpis"][:3]}


# ------------------------------------------------------------------ 设备台账
@router.get("/devices")
def list_devices(keyword: str = "", type: str = "", status: str = "",
                 region: str = "", vendor: str = "", group: str = "",
                 online: str = "", name: str = "", role: str = "", model: str = "",
                 version: str = "", ip: str = "", owner: str = "", location: str = "",
                 asset_no: str = "", usage: str = "", warranty_until: str = "",
                 note: str = "",
                 page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                 sort: str = "ip", order: str = "asc", pending: int = Query(0, ge=0, le=1)):
    rows, source, info = service.devices_view(pending=bool(pending))
    filtered = []
    location_query = (location or "").strip().lower()
    for dev in rows:
        if type and type != "all":
            # 页面上的「服务器 / 网络设备」是两大类，防火墙与无线控制器归在网络设备里
            if type == "server":
                if dev["group_kind"] != "server":
                    continue
            elif type in ("switch", "security"):
                if dev["group_kind"] != type:
                    continue
            elif dev["kind"] != type:
                continue
        if status and status not in ("all", dev["health_status"]):
            continue
        if region and region != "all" and dev["region"] != region:
            continue
        if vendor and vendor != "all" and dev["vendor_display"] != vendor:
            continue
        if group and group != "all" and dev["group"] != group:
            continue
        if location_query and location_query not in \
                ((dev.get("ledger") or {}).get("location") or "").lower():
            continue
        if online in ("1", "true", "yes"):
            if not dev["online"]:
                continue
        elif online in ("0", "false", "no"):
            if dev["online"]:
                continue
        if keyword:
            blob = " ".join([dev["name"], dev.get("role") or "", dev["ip"], dev["model"], dev["serial"],
                             dev["vendor_display"], dev["group"],
                             dev["ledger"].get("usage") or "",
                             dev["ledger"].get("owner") or "",
                             dev["ledger"].get("asset_no") or "",
                             dev["ledger"].get("location") or "",
                             dev["ledger"].get("warranty_until") or "",
                             dev["ledger"].get("note") or ""]).lower()
            if keyword.lower() not in blob:
                continue
        field_blob = {
            "name": dev.get("name") or "",
            "role": dev.get("role") or "",
            "usage": (dev.get("ledger") or {}).get("usage") or "",
            "model": dev.get("model") or "",
            "version": dev.get("version") or "",
            "ip": dev.get("ip") or "",
            "owner": (dev.get("ledger") or {}).get("owner") or "",
            "location": (dev.get("ledger") or {}).get("location") or "",
            "asset_no": (dev.get("ledger") or {}).get("asset_no") or "",
            "warranty_until": (dev.get("ledger") or {}).get("warranty_until") or "",
            "note": (dev.get("ledger") or {}).get("note") or "",
        }
        if any(value and value.lower() not in field_blob[field].lower()
               for field, value in (("name", name), ("role", role), ("model", model),
                                    ("version", version), ("ip", ip),
                                    ("owner", owner), ("location", location),
                                    ("asset_no", asset_no), ("usage", usage),
                                    ("warranty_until", warranty_until), ("note", note))):
            continue
        filtered.append(dev)

    SORTS = {"ip", "name", "health_score", "last_inspected_at", "type_label", "group"}
    sort = sort if sort in SORTS else "ip"

    def sort_key(dev):
        value = dev.get(sort)
        if value is None:
            value = ""
        return (str(value).isdigit() and int(str(value)) or 0, str(value))

    if sort == "ip":
        def sort_key(dev):
            parts = (dev["ip"] or "").split(".")
            return tuple(int(p) if p.isdigit() else 0 for p in parts)
    elif sort == "health_score":
        def sort_key(dev):
            return dev["health_score"] if dev["health_score"] is not None else -1
    elif sort == "name":
        def sort_key(dev):
            return (dev["name"] or "").lower()
    elif sort in ("type_label", "group"):
        def sort_key(dev):
            return (dev.get(sort) or "", dev["ip"] or "")
    elif sort == "last_inspected_at":
        def sort_key(dev):
            return dev.get("last_inspected_at") or ""
    reverse = order.lower() == "desc"
    filtered.sort(key=sort_key, reverse=reverse)

    total = len(filtered)
    start = (page - 1) * page_size
    page_rows = filtered[start:start + page_size]
    kinds: dict = {}
    groups: dict = {}
    vendors_map: dict = {}
    regions_map: dict = {}
    for dev in rows:
        bucket = kinds.setdefault(dev["kind"], {"value": dev["kind"],
                                               "label": dev["type_label"], "count": 0})
        bucket["count"] += 1
        if dev["group"]:
            groups[dev["group"]] = groups.get(dev["group"], 0) + 1
        if dev["vendor_display"]:
            vendors_map[dev["vendor_display"]] = vendors_map.get(dev["vendor_display"], 0) + 1
        if dev["region"]:
            regions_map[dev["region"]] = regions_map.get(dev["region"], 0) + 1
    return {
        "source": source, "source_info": info,
        "source_label": service.source_label(source), "pending": bool(pending),
        "total": total, "page": page, "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "rows": page_rows,
        "summary": {"total": len(rows),
                    "online": len([d for d in rows if d["online"]]),
                    "servers": len([d for d in rows if d["group_kind"] == "server"]),
                    "switches": len([d for d in rows if d["group_kind"] == "switch"]),
                    "security": len([d for d in rows if d["group_kind"] == "security"]),
                    "abnormal": len([d for d in rows if d["health_status"] in ("warning", "danger")]),
                    "types": [{"value": k, "label": v["label"], "count": v["count"]}
                              for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]["count"])]},
        "facets": {
            "vendors": [{"value": k, "label": k, "count": v}
                        for k, v in sorted(vendors_map.items(), key=lambda kv: -kv[1])],
            "regions": [{"value": k, "label": k, "count": v}
                        for k, v in sorted(regions_map.items(), key=lambda kv: -kv[1])],
            "groups": [{"value": k, "label": k, "count": v}
                       for k, v in sorted(groups.items(), key=lambda kv: -kv[1])],
            "types": [{"value": k, "label": v["label"], "count": v["count"]}
                       for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]["count"])],
        },
        "filter": {"keyword": keyword, "type": type, "status": status,
                   "region": region, "vendor": vendor, "group": group,
                   "online": online, "name": name, "role": role, "model": model,
                   "version": version, "ip": ip, "owner": owner,
                   "location": location,
                   "asset_no": asset_no, "usage": usage,
                   "warranty_until": warranty_until, "note": note,
                   "sort": sort, "order": order},
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/devices/demo-candidates")
def demo_candidates():
    """测试数据清理候选：10.20.* 或台账备注含“演示”的设备。"""
    return {"devices": get_store().demo_device_candidates()}


@router.get("/devices/{key}")
def device_detail(key: str):
    data = service.device_detail(key)
    if not data.get("device"):
        raise HTTPException(404, "设备不存在（先到「设备清单」新增该设备）")
    return data


@router.put("/devices/{key}/ledger")
def save_ledger(key: str, payload: dict):
    """台账补充字段：资产编号 / 责任人 / 用途 / 地点 / 维保到期 / 类型纠正 / 备注。"""
    data = service.device_detail(key)
    dev = data.get("device")
    if not dev:
        raise HTTPException(404, "设备不存在")
    saved = service.get_store().ledger_save(dev["ip"], dict(payload or {},
                                                           device_id=dev["id"],
                                                           device_name=dev["name"]))
    service.cache_clear()
    return {"ok": True, "ledger": saved}


@router.get("/devices/{key}/alerts")
def device_alerts(key: str, hours: int = Query(24 * 90, ge=1, le=24 * 365)):
    dev = service.device_detail(key).get("device")
    if not dev:
        raise HTTPException(404, "设备不存在")
    return service.alert_board(hours=hours, device=dev["ip"], limit=50)


# ------------------------------------------------------------------ 健康检查
@router.get("/health/server")
def health_server(device: str = ""):
    return service.health_page("server", device or None)


@router.get("/health/switch")
def health_switch(device: str = ""):
    return service.health_page("switch", device or None)


@router.get("/health/security")
def health_security(device: str = ""):
    return service.health_page("security", device or None)


# ------------------------------------------------------------------ 告警 / 巡检 / 备份
@router.get("/alerts")
def list_alerts(hours: int = Query(24 * 30, ge=1, le=24 * 365), severity: str = "",
                status: str = "", device: str = "", source: str = "",
                keyword: str = "", limit: int = Query(100, ge=1, le=500)):
    return service.alert_board(hours=hours, severity=severity, status=status,
                               device=device, source_key=source,
                               keyword=keyword, limit=limit)


@router.post("/alerts/disposition")
def dispose_alerts(request: Request, payload: dict = Body(...)):
    """确认 / 恢复 / 关闭一组告警，并记录处置人、责任人和备注。"""
    user = request.state.user
    ids = (payload or {}).get("ids") or []
    status = (payload or {}).get("status") or ""
    assignee = (payload or {}).get("assignee") or ""
    note = (payload or {}).get("note") or ""
    try:
        changed = get_store().alert_disposition(
            ids, status, assignee=assignee, note=note, actor=user["username"])
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    service.cache_clear()
    auth.log_event(user["username"], "alert_disposition",
                   "处置 %d 条告警：%s %s %s" % (changed, status, assignee, note),
                   operator=user["username"], target_type="alerts")
    return {"ok": True, "changed": changed, "status": status}


@router.get("/inspections")
def list_inspections(hours: int = Query(24 * 90, ge=1, le=24 * 365),
                     kind: str = "", limit: int = Query(200, ge=1, le=2000),
                     keyword: str = "", healthy: str = "", page: int = Query(1, ge=1),
                     page_size: int = Query(20, ge=1, le=200)):
    data = service.inspection_rows(hours=hours, limit=2000, kind=kind)
    rows = data["rows"]
    kw = (keyword or "").strip().lower()
    if kw:
        rows = [r for r in rows
                if kw in " ".join([r["device"], r["device_ip"], r["type"], r["issues"],
                                   r.get("owner") or "", r.get("asset_no") or "",
                                   r.get("location") or ""]).lower()]
    if healthy in ("1", "true", "yes"):
        rows = [r for r in rows if r["healthy"]]
    elif healthy in ("0", "false", "no"):
        rows = [r for r in rows if not r["healthy"]]
    page_size = max(1, page_size)
    total = len(rows)
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(1, page), pages)
    data["rows"] = rows[(page - 1) * page_size: page * page_size]
    data.update({"total": total, "matched": total, "page": page, "pages": pages,
                 "page_size": page_size, "keyword": keyword, "healthy": healthy})
    return data


# ------------------------------------------------------------------ 全局搜索 / 审计 / 账号 / 模板
@router.get("/search")
def global_search(q: str = "", limit: int = Query(8, ge=1, le=50)):
    """顶栏搜索：设备 / 告警 / 备份 一次搜，返回分组结果。"""
    return service.search(q, limit)


@router.get("/audit")
def audit(hours: int = Query(24 * 7, ge=1, le=24 * 365), username: str = "",
          action: str = "", q: str = "", limit: int = Query(200, ge=1, le=500)):
    return service.audit_rows(hours=hours, username=username, action=action,
                              keyword=q, limit=limit)


@router.get("/users")
def users(hours: int = Query(24 * 30, ge=1, le=24 * 365), username: str = "",
          action: str = "", q: str = "", limit: int = Query(200, ge=1, le=500)):
    """令牌身份 + 账号审计（过滤参数与 /api/audit 一致，前端一次拿全）。"""
    return service.users_overview(hours=hours, username=username, action=action,
                                  keyword=q, limit=limit)


@router.get("/templates")
def templates():
    return service.templates_meta()


# ------------------------------------------------------------------ 台账补充：批量
@router.get("/ledger")
def ledger_export():
    return service.ledger_export()


def _csv_response(text: str, filename: str):
    """CSV 下载统一响应：UTF-8 BOM（Excel 双击不乱码）+ 中文文件名。"""
    from fastapi.responses import Response
    from urllib.parse import quote
    body = ("\ufeff" + text).encode("utf-8")
    return Response(content=body, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": "attachment; filename*=UTF-8''%s" % quote(filename),
        "Access-Control-Expose-Headers": "Content-Disposition",
    })


@router.get("/ledger/template.csv")
def ledger_template():
    """导入模板：**列与「设备清单」一致**——身份列（名称/类型/型号/版本/分组/健康状态）已按设备填好，
    只有后面的台账补充列需要填；另带一行示例行（可删）。"""
    devices, _, _ = service.devices_view()
    lines = [service.ledger_csv_header(), service.ledger_csv_example()]
    lines.extend(service.ledger_csv_rows(include_values=False))
    return _csv_response("\n".join(lines) + "\n", "台账导入模板.csv")


@router.get("/ledger/export.csv")
def ledger_export_csv():
    """把当前台账导成 CSV（列名与导入模板一致，改完直接导回来）。"""
    return _csv_response(service.ledger_csv_export(), "设备台账台账补充.csv")


@router.post("/ledger/import")
def ledger_import(request: Request, payload: dict = Body(...)):
    """按 IP 批量导入台账补充字段。

    `csv` 放 CSV 文本；`dry_run=true` 只预检不写库（返回逐行「新增/更新/跳过/报错」）。
    """
    payload = payload or {}
    text = payload.get("csv") or ""
    if not text.strip():
        raise HTTPException(400, "CSV 内容为空")
    operator = request.state.user["username"]
    result = service.ledger_import(text, operator=operator,
                                   dry_run=bool(payload.get("dry_run")),
                                   clear_empty=bool(payload.get("clear_empty")))
    result["ledger"] = service.ledger_export()["total"]
    result["operator"] = operator
    return result


@router.get("/backups")
def list_backups(keyword: str = "", page: int = Query(1, ge=1),
                 page_size: int = Query(20, ge=1, le=200)):
    return service.backup_overview(keyword=keyword, page=page, page_size=page_size)


@router.get("/backups/package")
def package_backups(device: str = ""):
    """实时抓取交换机配置/服务器备份并打包 ZIP 直接下载（内存生成，不落盘）。"""
    from fastapi.responses import Response
    from urllib.parse import quote
    try:
        filename, payload, meta = service.package_configs(device)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:                            # noqa: BLE001
        raise HTTPException(500, "打包配置失败：%s" % exc)
    return Response(content=payload, media_type="application/zip", headers={
        "Content-Disposition": "attachment; filename*=UTF-8''%s" % quote(filename),
        "X-Package-Ok": str(meta.get("ok") or 0),
        "X-Package-Failed": str(meta.get("failed") or 0),
        "X-Package-Files": str(meta.get("files") or 0),
        "Access-Control-Expose-Headers": "Content-Disposition, X-Package-Ok, X-Package-Failed, X-Package-Files",
    })




