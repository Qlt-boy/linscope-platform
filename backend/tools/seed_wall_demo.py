# -*- coding: utf-8 -*-
"""生成巡检大屏演示数据：三类设备各 10 台，每台 12 个动态时间节点。

只操作 10.20.110.* / 10.20.120.* / 10.20.130.*，可重复执行，不影响真实设备。
所有记录标注“演示数据”，可在设备清单的“清理测试数据”窗口删除。
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, timedelta

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import service  # noqa: E402
from app.store import get_store, next_row_id  # noqa: E402

PREFIXES = ("10.20.110.", "10.20.120.", "10.20.130.")
POINTS = 12
STEP_MINUTES = 5

CATEGORIES = [
    dict(prefix="10.20.110.", tag="SW", kind="switch", override="core_switch",
         group="演示交换机", usage="演示核心交换机", vendor="huawei", vendor_display="华为",
         model="S12700E-4", version="VRP (R) software, Version 5.170"),
    dict(prefix="10.20.120.", tag="SRV", kind="server", override="server",
         group="演示服务器", usage="演示业务服务器", vendor="dell", vendor_display="戴尔",
         model="PowerEdge R750", version="Ubuntu 24.04.5 LTS"),
    dict(prefix="10.20.130.", tag="SEC", kind="security", override="security",
         group="演示安全设备", usage="演示边界防火墙", vendor="huawei", vendor_display="华为",
         model="USG6650E", version="VRP (R) software, Version 5.170"),
]


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def clamp(value: float) -> float:
    return max(0.0, min(100.0, round(value, 1)))


def wipe(store) -> int:
    removed = 0
    tables = (
        ("inspections", "device_ip"), ("monitors", "device_ip"),
        ("metrics", "device_ip"), ("alerts", "device_ip"),
        ("backups", "device_ip"), ("ledger", "device_ip"),
        ("credentials", "ip"), ("collect_logs", "device_ip"),
        ("remote_commands", "device_ip"), ("remote_sessions", "device_ip"),
    )
    with store.connect() as conn:
        for prefix in PREFIXES:
            removed += conn.execute(
                "SELECT count(*) FROM devices WHERE ip LIKE ?", (prefix + "%",)).fetchone()[0]
            for table, column in tables:
                conn.execute("DELETE FROM %s WHERE %s LIKE ?" % (table, column), (prefix + "%",))
            conn.execute("DELETE FROM devices WHERE ip LIKE ?", (prefix + "%",))
    service.cache_clear()
    return removed


def seed() -> dict:
    store = get_store()
    wipe(store)
    now = datetime.now().replace(second=0, microsecond=0)
    monitors = []
    inspections = []
    metrics = []
    alerts = []
    created = 0
    for ci, category in enumerate(CATEGORIES):
        for index in range(1, 11):
            ip = category["prefix"] + str(index)
            name = "DEMO-%s-%02d" % (category["tag"], index)
            base_health = 52.0 + (index - 1) * 4.6
            phase = index * 0.63 + ci * 0.8
            device = {
                "ip": ip, "name": name, "vendor": category["vendor"],
                "vendor_display": category["vendor_display"], "model": category["model"],
                "serial": "DEMO-%s-%02d" % (category["tag"], index),
                "version": category["version"], "role": category["kind"],
                "kind": category["kind"], "group": category["group"], "region": "演示区",
                "online": True, "port": 22, "source": "local",
                "last_online_at": stamp(now),
            }
            store.device_upsert(device)
            dev = store.device_get(ip)
            device_id = dev.get("id")
            store.ledger_save(ip, {
                "device_id": device_id, "device_name": name,
                "asset_no": "DEMO-%s-%02d" % (category["tag"], index),
                "owner": "演示账号", "usage": category["usage"],
                "location": "演示机柜", "kind_override": category["override"],
                "note": "演示数据：大屏动态曲线",
            })
            latest_cpu = latest_mem = latest_health = latest_disk = latest_temp = None
            for point in range(POINTS):
                when = now - timedelta(minutes=(POINTS - 1 - point) * STEP_MINUTES)
                wave = math.sin(point * 0.68 + phase) * 8.0
                drift = (point - (POINTS - 1) / 2.0) * (0.8 if index % 2 else -0.7)
                health = clamp(base_health + wave + drift)
                cpu = clamp(100 - health + 8 + math.sin(point * 0.52 + phase) * 12)
                memory = clamp(100 - health + 16 + math.cos(point * 0.47 + phase) * 10)
                latest_cpu, latest_mem, latest_health = cpu, memory, health
                monitors.append({
                    "id": next_row_id(), "device_id": device_id, "device": name,
                    "device_ip": ip, "sysname": name, "serial": device["serial"],
                    "version": device["version"], "cpu": cpu, "memory": memory,
                    "health_score": health, "ok": True, "error": "",
                    "collected_at": stamp(when), "source": "demo",
                })
                issues = ""
                if health < 85:
                    issues = "演示异常：健康度 %.1f 低于 85" % health
                elif health < 95:
                    issues = "演示关注：健康度 %.1f" % health
                port_count = 48 if category["kind"] == "switch" else (8 if category["kind"] == "server" else 12)
                ports = [{"name": ("GigabitEthernet0/0/%d" % n if category["kind"] == "switch"
                                    else ("eth%d" % n if category["kind"] == "server" else "GE1/0/%d" % n)),
                          "up": (n + point + index) % 8 != 0}
                         for n in range(1, port_count + 1)]
                inspections.append({
                    "id": next_row_id(), "run_id": "DEMO-WALL", "device_id": device_id,
                    "device": name, "device_ip": ip, "cpu": cpu, "memory": memory,
                    "health_score": health, "stp_state": "enabled", "stp_mode": "MSTP",
                    "stp_forward": 42 + index % 5, "stp_blocked": 2 + index % 4,
                    "error_ports": index % 4, "error_total": index * 3 % 20,
                    "healthy": health >= 85, "issues": issues, "error": "",
                    "inspected_at": stamp(when), "ports": ports, "lldp": [],
                    "uptime_text": "%d days" % (100 + index), "uptime_seconds": 86400 * (100 + index),
                })
                if category["kind"] == "server":
                    latest_disk = clamp(45 + index * 4 + math.sin(point + phase) * 8)
                    latest_temp = round(32 + index * 0.9 + math.cos(point + phase) * 2, 1)
            alert_count = (index + ci * 2) % 4
            if health < 70:
                alert_count += 1
            for ai in range(alert_count):
                severity = ("critical" if ai == 0 and health < 60 else
                            "major" if ai <= 1 else "warning")
                content = [
                    "CPU 使用率持续偏高，当前 %.1f%%" % cpu,
                    "内存使用率持续偏高，当前 %.1f%%" % memory,
                    "关键接口存在错误包或状态异常",
                    "检测到持续性健康度下降趋势"
                ][(index + ai) % 4]
                alerts.append({
                    "id": next_row_id(), "source": "monitor", "source_display": "本平台采集",
                    "severity": severity, "status": "new", "device": name, "device_ip": ip,
                    "rule": "演示实时告警", "metric": "demo_alert_%d" % ai,
                    "value": health, "content": content, "dedupe_key": "demo_alert_%d" % ai,
                    "triggered_at": stamp(now - timedelta(minutes=ai * 7 + index)),
                })
            if category["kind"] == "server":
                metrics.append({
                    "id": next_row_id(), "device_id": device_id, "device": name,
                    "device_ip": ip, "metric": "disk", "label": "磁盘使用率",
                    "value": latest_disk, "unit": "%", "source": "demo",
                    "collected_at": stamp(now),
                })
                metrics.append({
                    "id": next_row_id(), "device_id": device_id, "device": name,
                    "device_ip": ip, "metric": "temp", "label": "机箱温度",
                    "value": latest_temp, "unit": "℃", "source": "demo",
                    "collected_at": stamp(now),
                })
            created += 1
    store.save_monitors(monitors)
    store.save_inspections(inspections)
    if metrics:
        store.save_metrics(metrics)
    if alerts:
        store.save_alerts(alerts)
    service.cache_clear()
    return {"devices": created, "points": POINTS, "monitors": len(monitors),
            "inspections": len(inspections), "metrics": len(metrics), "alerts": len(alerts)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear", action="store_true", help="只删除大屏演示设备")
    args = ap.parse_args()
    store = get_store()
    if args.clear:
        print("已删除大屏演示设备 %d 台" % wipe(store))
        return 0
    result = seed()
    print("大屏演示数据已生成：设备 %(devices)d 台 × %(points)d 个时间点；监控 %(monitors)d 条，巡检 %(inspections)d 条，告警 %(alerts)d 条" % result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
