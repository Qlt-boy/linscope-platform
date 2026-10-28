# -*- coding: utf-8 -*-
"""导入设备清单图片中的正式设备台账（无 IP 设备使用稳定 noip-NNN 台账键）。"""
from __future__ import annotations
import csv
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
from app import service  # noqa: E402
from app.store import get_store  # noqa: E402

DATA_FILE = Path(__file__).with_name("inventory_devices_import.psv")


def load_rows():
    with DATA_FILE.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="|"))


def main() -> int:
    rows = load_rows()
    store = get_store()
    added = updated = 0
    for index, row in enumerate(rows, 1):
        real_ip = (row.get("ip") or "").strip()
        ip = real_ip or "noip-%03d" % index
        existed = bool(store.device_get(ip))
        device = {
            "ip": ip, "name": row["name"], "vendor": row["vendor"],
            "vendor_display": row["vendor_display"], "model": row["model"],
            "version": row["version"], "role": row["role"], "group": row["group"],
            "region": row["region"], "port": 22, "source": "inventory-import",
            "inventory_source": "设备清单图片", "management_ip_missing": not bool(real_ip),
        }
        if not existed:
            device["online"] = False
            added += 1
        else:
            updated += 1
        store.device_upsert(device)
        dev = store.device_get(ip) or {}
        store.ledger_save(ip, {
            "device_id": dev.get("id"), "device_name": row["name"],
            "asset_no": "IMG-%03d" % index, "owner": "", "usage": row["role"],
            "location": row["location"], "kind_override": row["kind"],
            "note": row["note"] or "设备清单图片导入；待补充管理IP、采集凭据；未生成模拟巡检数据。",
        })
    service.cache_clear()
    print("设备清单导入完成：新增 %d 台，更新 %d 台，共 %d 台" % (added, updated, len(rows)))
    print("其中待补管理 IP 的台账设备：%d 台" % len([r for r in rows if not (r.get("ip") or "").strip()]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())