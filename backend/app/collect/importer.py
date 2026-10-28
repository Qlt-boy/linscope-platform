# -*- coding: utf-8 -*-
"""设备台账 CSV 批量导入（自带采集模式下用来一次性录入一批交换机）。"""
from __future__ import annotations

import csv
import io

from ..store import get_store
from ..device_fields import normalize_management_ip

HEADER_MAP = {
    "序列号": "serial", "serial": "serial", "设备序列号": "serial",
    "设备角色": "role", "role": "role",
    "ip": "ip", "ip地址": "ip", "ip 地址": "ip", "管理ip": "ip", "地址": "ip",
    "资产编号": "asset_no", "资产号": "asset_no",
    "责任人": "owner", "负责人": "owner", "运维责任人": "owner",
    "设备用途": "usage", "用途": "usage",
    "设备地点": "location", "地点": "location", "位置": "location",
    "维保到期": "warranty_until", "维保到期日": "warranty_until", "保修到期": "warranty_until",
    "备注": "note", "说明": "note",
}

#: 导入阶段只录入身份（IP）和业务自定义字段。设备名称、类型、型号、版本等
#: 由采集成功后回填，避免把人工占位值误当成采集结果。
CUSTOM_FIELDS = ("asset_no", "owner", "usage", "location", "warranty_until", "note")
DEVICE_IMPORT_HEADERS = ["序列号", "设备角色", "IP地址", "设备地点"]
DEVICE_IMPORT_SAMPLE = ["LAB-SW-001", "核心交换机", "10.10.9.1", "信息中心机房"]


def device_import_template_csv() -> str:
    """设备采集四字段模板：序列号、设备角色、IP、设备地点。"""
    import csv
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(DEVICE_IMPORT_HEADERS)
    writer.writerow(DEVICE_IMPORT_SAMPLE)
    return buffer.getvalue()


def import_devices_csv(text: str, dry_run: bool = False) -> dict:
    store = get_store()
    reader = csv.DictReader(io.StringIO((text or "").lstrip("\ufeff")))
    headers = reader.fieldnames or []
    if not any(HEADER_MAP.get(str(key).strip().lower()) == "ip" for key in headers):
        return {"ok": False, "dry_run": bool(dry_run), "created": 0, "updated": 0,
                "error_count": 1, "errors": ["CSV 为空或缺少 IP地址 表头"],
                "details": [{"line": 1, "ip": "", "action": "error", "message": "CSV 为空或缺少 IP地址 表头"}],
                "total": 0, "devices_total": len(store.devices())}
    created = updated = 0
    errors: list[str] = []
    details: list[dict] = []
    seen = set()
    for index, raw in enumerate(reader, start=2):
        row = {}
        for key, value in (raw or {}).items():
            if not key:
                continue
            target = HEADER_MAP.get(str(key).strip().lower()) or HEADER_MAP.get(str(key).strip())
            if target:
                row[target] = (value or "").strip() if isinstance(value, str) else value
        ip = row.get("ip") or ""
        if not ip and not any(row.values()):
            continue
        if not ip:
            errors.append("第 %d 行：缺少 IP" % index)
            details.append({"line": index, "ip": "", "action": "error",
                            "message": "缺少 IP 列"})
            continue
        try:
            ip = normalize_management_ip(ip)
        except ValueError as exc:
            errors.append("第 %d 行：%s" % (index, exc))
            details.append({"line": index, "ip": ip, "action": "error", "message": str(exc)})
            continue
        if ip in seen:
            errors.append("第 %d 行：IP %s 重复" % (index, ip))
            details.append({"line": index, "ip": ip, "action": "error",
                            "message": "同一文件里 IP 重复（只保留第一条）"})
            continue
        seen.add(ip)
        existed = bool(store.device_get(ip))
        if dry_run:
            details.append({"line": index, "ip": ip,
                            "action": "would_update" if existed else "would_create",
                            "message": ("将更新设备信息" if existed else "将加入待采集区")})
            continue
        device = store.device_get(ip) or {"ip": ip, "online": False,
                                          "pending_collection": True,
                                          "vendor": "huawei", "vendor_display": "华为"}
        for key in ("serial", "role"):
            if row.get(key):
                device[key] = row[key]
        device["source"] = "local"
        store.device_upsert(device)
        saved = store.device_get(ip) or device
        ledger_values = {key: row.get(key) for key in CUSTOM_FIELDS if row.get(key)}
        if ledger_values:
            ledger_values["device_id"] = saved.get("id")
            ledger_values["device_name"] = saved.get("name") or ip
            store.ledger_save(ip, ledger_values)
        if existed:
            updated += 1
            details.append({"line": index, "ip": ip, "action": "update",
                            "name": device.get("name") or "", "message": "已更新设备信息"})
        else:
            created += 1
            details.append({"line": index, "ip": ip, "action": "create",
                            "name": device.get("name") or "", "message": "已加入待采集区"})
    return {"ok": not errors or (created + updated) > 0, "dry_run": bool(dry_run),
            "created": created, "updated": updated, "error_count": len(errors),
            "errors": errors[:40], "details": details[:200],
            "total": created + updated,
            "devices_total": len(store.devices())}