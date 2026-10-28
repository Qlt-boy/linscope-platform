# -*- coding: utf-8 -*-
"""自带采集接口：设备台账维护 + 手动/定时采集 + 采集日志。"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import Response

from .. import auth, collect as collect_pkg, service
from ..collect import runner
from ..store import get_store
from ..device_fields import normalize_management_ip

router = APIRouter(prefix="/api/collect", tags=["collect"])
devices_router = APIRouter(prefix="/api/devices", tags=["devices-local"])

EDITABLE_DEVICE_FIELDS = ("name", "model", "serial", "version", "role", "group",
                          "region", "port", "vendor", "vendor_display", "kind")


@router.get("/overview")
def overview(pending_only: int = Query(0, ge=0, le=1)):
    """采集页数据；pending_only=1 时仅返回待采集设备。"""
    return runner.overview(pending_only=bool(pending_only))


@router.get("/settings")
def get_settings():
    return runner.settings()


@router.post("/settings")
def post_settings(request: Request, payload: dict = Body(...)):
    user = request.state.user
    saved = runner.save_settings(payload or {})
    auth.log_event(user["username"], "collect_settings", "修改采集设置",
                   operator=user["username"], target_type="collect")
    return {"ok": True, "settings": saved}


@router.post("/run")
def run_now(request: Request, payload: dict = Body(default={})):
    """立即采集：`ips` 指定设备（留空=全部），`with_config` 是否顺带抓配置备份。"""
    payload = payload or {}
    ips = payload.get("ips") or None
    if isinstance(ips, str):
        ips = [x.strip() for x in ips.split(",") if x.strip()]
    try:
        user = request.state.user
        result = runner.run(ips=ips, trigger="manual",
                            with_config=payload.get("with_config"),
                            operator=user["username"])
        auth.log_event(user["username"], "collect_run",
                       "手动采集：%s" % result.get("message", ""),
                       operator=user["username"], target_type="collect")
        return result
    except Exception as exc:                          # noqa: BLE001
        raise HTTPException(500, "采集失败：%s" % exc)


@router.get("/runs")
def runs(limit: int = Query(20, ge=1, le=200)):
    store = get_store()
    rows = store.collect_runs(limit=limit)
    return {"runs": rows, "total": len(rows)}


@router.post("/precheck")
def precheck(payload: dict = Body(default={})):
    """采集前连通性预检（TCP 探测，不登录）：返回每台是否可达、耗时与失败原因。"""
    payload = payload or {}
    ips = payload.get("ips") or None
    if isinstance(ips, str):
        ips = [x.strip() for x in ips.split(",") if x.strip()]
    timeout = float(payload.get("timeout") or 2.5)
    return runner.precheck(ips=ips, timeout=max(0.5, min(10.0, timeout)))


@router.get("/logs/export.csv")
def export_logs(ip: str = "", run_id: int = Query(0, ge=0),
                only_failed: int = Query(0, ge=0, le=1),
                with_raw: int = Query(0, ge=0, le=1),
                limit: int = Query(1000, ge=1, le=5000)):
    """采集日志导出 CSV（可选是否带原始回显摘要）。"""
    from urllib.parse import quote

    from fastapi.responses import Response
    text = runner.logs_csv(ip=ip, only_failed=bool(only_failed), run_id=run_id,
                           limit=limit, with_raw=bool(with_raw))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = "采集日志-%s.csv" % stamp
    return Response(content=("\ufeff" + text).encode("utf-8"),
                    media_type="text/csv; charset=utf-8",
                    headers={
                        "Content-Disposition":
                            "attachment; filename*=UTF-8''%s" % quote(name),
                        "Access-Control-Expose-Headers": "Content-Disposition",
                    })


@router.get("/logs")
def logs(ip: str = "", run_id: int = Query(0, ge=0),
         only_failed: int = Query(0, ge=0, le=1),
         limit: int = Query(50, ge=1, le=500)):
    """采集日志（列表不带原始回显，点详情才取）。"""
    store = get_store()
    rows = store.collect_logs(ip=ip, limit=limit, run_id=run_id,
                              only_failed=bool(only_failed), with_raw=False)
    return {"logs": rows, "total": len(rows), "filter": {
        "ip": ip, "run_id": run_id, "only_failed": bool(only_failed)}}


@router.get("/logs/{log_id}")
def log_detail(log_id: int):
    """单条采集日志：含执行过的命令与**原始回显摘要**（排错用）。"""
    store = get_store()
    row = store.collect_log_get(log_id)
    if not row:
        raise HTTPException(404, "采集日志不存在")
    return row


@router.post("/purge")
def purge(request: Request, payload: dict = Body(default={})):
    """清理历史采集日志（默认保留 30 天）。"""
    keep_days = int((payload or {}).get("keep_days") or 30)
    user = request.state.user
    removed = get_store().purge_collect_logs(keep_days)
    auth.log_event(user["username"], "collect_purge",
                   "清理采集日志：保留 %d 天，删除 %d 条" % (keep_days, removed),
                   operator=user["username"], target_type="collect")
    return {"ok": True, "removed": removed, "keep_days": keep_days}


# ------------------------------------------------------------------ 设备台账（本平台维护）
@devices_router.post("")
def create_device(request: Request, request_payload: dict = Body(...)):
    """新增设备（自带采集模式下，台账由本平台维护）。"""
    try:
        ip = normalize_management_ip((request_payload or {}).get("ip"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    if not ip:
        raise HTTPException(400, "IP 地址不能为空")
    store = get_store()
    if store.device_get(ip):
        raise HTTPException(400, "设备 %s 已存在" % ip)
    device = {"ip": ip, "online": False, "pending_collection": True,
              "vendor": "huawei", "vendor_display": "华为", "source": "local"}
    for key in EDITABLE_DEVICE_FIELDS:
        if request_payload.get(key) is not None:
            device[key] = str(request_payload[key]).strip()
    store.device_upsert(device)
    service.cache_clear()
    auth.log_event(request.state.user["username"], "device_create", "新增设备 %s" % ip,
                   operator=request.state.user["username"], target_type="device")
    return {"ok": True, "device": store.device_get(ip)}


@devices_router.put("/{ip}")
def update_device(ip: str, request: Request, payload: dict = Body(...)):
    store = get_store()
    device = store.device_get(ip)
    if not device:
        raise HTTPException(404, "设备不存在")
    for key in EDITABLE_DEVICE_FIELDS:
        if payload.get(key) is not None:
            device[key] = str(payload[key]).strip()
    if "online" in payload:
        device["online"] = bool(payload["online"])
    store.device_upsert(device)
    service.cache_clear()
    auth.log_event(request.state.user["username"], "device_update", "修改设备 %s" % ip,
                   operator=request.state.user["username"], target_type="device")
    return {"ok": True, "device": store.device_get(ip)}


@devices_router.delete("/{ip}")
def delete_device(ip: str, request: Request,
                  purge_history: int = Query(1, ge=0, le=1)):
    store = get_store()
    existed = store.device_delete(ip, purge_history=bool(purge_history))
    service.cache_clear()
    auth.log_event(request.state.user["username"], "device_delete",
                   "删除设备 %s；清理关联数据=%s；设备已存在=%s"
                   % (ip, bool(purge_history), existed),
                   operator=request.state.user["username"], target_type="device")
    # 删除是幂等操作：旧页面重复点击或缓存竞态时仍返回成功，避免“设备不存在”。
    return {"ok": True, "ip": ip, "purge_history": bool(purge_history),
            "already_missing": not existed}


@devices_router.post("/purge-demo")
def purge_demo(request: Request, payload: dict = Body(...)):
    """按预览勾选批量清理演示设备；只允许删除候选列表中的设备。"""
    if (payload or {}).get("confirm") != "PURGE_DEMO":
        raise HTTPException(400, "缺少清理确认标记")
    candidates = {x["ip"]: x for x in get_store().demo_device_candidates()}
    ips = [str(x).strip() for x in ((payload or {}).get("ips") or []) if str(x).strip()]
    if not ips:
        raise HTTPException(400, "没有选择要清理的设备")
    invalid = [ip for ip in ips if ip not in candidates]
    if invalid:
        raise HTTPException(400, "以下设备不在测试数据候选列表：%s" % "、".join(invalid))
    purge_history = bool((payload or {}).get("purge_history", True))
    removed = []
    for ip in ips:
        if get_store().device_delete(ip, purge_history=purge_history):
            removed.append(ip)
    service.cache_clear()
    auth.log_event(request.state.user["username"], "demo_device_purge",
                   "清理测试设备 %d 台：%s；关联数据=%s"
                   % (len(removed), "、".join(removed), purge_history),
                   operator=request.state.user["username"], target_type="device")
    return {"ok": True, "removed": removed, "count": len(removed),
            "purge_history": purge_history}


@router.get("/device-template.csv")
def device_import_template():
    """最小设备导入模板：只包含 IP 和业务自定义字段。"""
    text = "\ufeff" + collect_pkg.device_import_template_csv()
    return Response(
        content=text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''device-import-template.csv"},
    )


@devices_router.post("/import")
def import_devices(request: Request, payload: dict = Body(...)):
    """CSV 批量导入设备台账：列名认 `ip` / `设备名称` / `品牌型号` / `序列号` / `分组` / `地区` / `端口`。

    与台账补充导入一样：默认「空单元格不改动」，可 `replace=true` 覆盖同名字段。
    """
    text = (payload or {}).get("csv") or ""
    if not text.strip():
        raise HTTPException(400, "CSV 内容为空")
    result = collect_pkg.import_devices_csv(text, dry_run=bool((payload or {}).get("dry_run")))
    service.cache_clear()
    return result