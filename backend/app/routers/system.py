# -*- coding: utf-8 -*-
"""系统接口：状态体检 / 元信息 / 平台标识设置。

数据全部来自本平台自己的采集库，没有外部巡检平台，也没有数据源切换。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import FileResponse
from urllib.parse import quote
import re

from .. import auth, backup, config, service
from ..store import get_store

router = APIRouter(prefix="/api/system", tags=["system"])

#: 可在「系统设置」页修改的字段（采集参数在 /api/collect/settings 里）
EDITABLE = ("site_name", "org_name", "period_days", "cache_ttl")


@router.get("/status")
def get_status():
    """本地数据体检：设备 / 巡检 / 告警 / 备份数量与最近一次采集。"""
    return service.status()


@router.get("/branding")
def get_branding():
    """登录前也能读取的平台标识（只返回名称，不暴露业务数据）。"""
    values = get_store().get_settings()
    return {"site_name": values.get("site_name") or config.DEFAULTS["site_name"],
            "org_name": values.get("org_name") or config.DEFAULTS["org_name"],
            "period_days": values.get("period_days") or config.DEFAULTS["period_days"]}

@router.get("/meta")
def get_meta():
    return service.meta()


@router.get("/health")
def health():
    return {"ok": True, "service": "net-inspect-platform", "version": "1.3.0"}


@router.get("/build")
def build():
    """当前前端构建版本，供已打开页面检测更新并自动刷新。"""
    index_path = config.FRONTEND_DIR / "index.html"
    try:
        text = index_path.read_text(encoding="utf-8")
        match = re.search(r"[?&]v=([^\"'& <]+)", text)
        version = match.group(1) if match else ""
    except OSError:
        version = ""
    return {"build": version}

@router.post("/settings")
def post_settings(payload: dict = Body(...)):
    store = get_store()
    values = {k: v for k, v in (payload or {}).items()
              if k in EDITABLE and v is not None}
    if "period_days" in values:
        try:
            values["period_days"] = str(int(str(values["period_days"]).strip()))
        except (TypeError, ValueError):
            raise HTTPException(400, "period_days 必须是整数天数")
    if "cache_ttl" in values:
        try:
            values["cache_ttl"] = str(max(1, int(str(values["cache_ttl"]).strip())))
        except (TypeError, ValueError):
            raise HTTPException(400, "cache_ttl 必须是整数秒")
    current = store.get_settings()
    store.save_settings(values)
    service.cache_clear()
    return {"ok": True, "before": {"period_days": current.get("period_days")},
            "settings": service.status()}


@router.get("/defaults")
def get_defaults():
    return {"defaults": config.default_settings()}


@router.get("/diagnostics")
def get_diagnostics():
    """运行体检：数据大小、磁盘余量、TLS 到期、调度器与最近备份。"""
    return backup.diagnostics()


@router.get("/backups")
def get_backups(limit: int = Query(20, ge=1, le=100)):
    return {"backups": backup.list_backups(limit=limit),
            "auto_backup_hours": backup.diagnostics().get("auto_backup_hours"),
            "backup_keep": backup._backup_keep()}


@router.post("/backups/run")
def run_backup(request: Request):
    user = request.state.user
    info = backup.create_backup("manual", user["username"])
    auth.log_event(user["username"], "system_backup", "生成平台备份 %s" % info["name"],
                   operator=user["username"], target_type="system")
    return {"ok": True, "backup": info}


@router.get("/backups/download")
def download_backup(name: str = Query(...)):
    path = backup.get_backup_path(name)
    if not path:
        raise HTTPException(404, "备份文件不存在")
    return FileResponse(path, filename=path.name, media_type="application/zip",
                        headers={"Content-Disposition":
                                 "attachment; filename*=UTF-8''%s" % quote(path.name)})

