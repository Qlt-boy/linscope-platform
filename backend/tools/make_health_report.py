# -*- coding: utf-8 -*-
"""生成版式报告（Word / PDF）的命令行工具。

用途：
1. 现场交付前先在本机出一份样例，核对版式与字段是否齐全；
2. 现场环境里导出服务器 / 交换机健康性检查报告（不经过 Web 界面）。

用法：

    # 用当前数据库（backend/data/netinspect.sqlite3）出两份报告
    python backend/tools/make_health_report.py --kind both --out .\reports-out

    # 只出某一台设备
    python backend/tools/make_health_report.py --kind switch --device 127.0.0.2

    # 测试数据：拷贝一份库到临时目录，补两台样例服务器与样例交换机后再出报告
    # （真实数据不动，报告落在 --out 目录）
    python backend/tools/make_health_report.py --kind both --demo --out .\reports-out

示例数据只写进**临时副本**，不会污染现场库。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


# ------------------------------------------------------------------ 样例数据
def _stamp(days_ago: float) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")


#: 样例数据的行号放在这一段里，跟真实采集数据的行号错开，避免撞号
DEMO_ID_BASE = 7000000000000000


def _row_id(when: str, salt: int) -> int:
    """由时间戳 + 盐算一个稳定且唯一的行号（同一秒内批量写入也不会互相覆盖）。"""
    digits = int(when.replace("-", "").replace(":", "").replace(" ", ""))
    return DEMO_ID_BASE + digits * 100 + int(salt)


DEMO_SERVERS = [
    {
        "ip": "10.20.30.11", "name": "SRV-APP-01", "model": "PowerEdge R750",
        "vendor": "dell", "vendor_display": "戴尔",
        "version": "Ubuntu 22.04.3 LTS", "group": "业务服务器",
        "region": "机房A", "online": True, "cpu": 34.0, "memory": 61.0,
        "ledger": {"asset_no": "ZC-SRV-0011", "owner": "李工", "usage": "应用服务器",
                   "location": "A 机房 3 号机柜 U12"},
        "alerts": [],
        "disk": 72.0, "temp": 38.5,
    },
    {
        "ip": "10.20.30.12", "name": "SRV-DB-01", "model": "ThinkSystem SR650",
        "vendor": "lenovo", "vendor_display": "联想",
        "version": "Red Hat Enterprise Linux 8.6", "group": "业务服务器",
        "region": "机房A", "online": True, "cpu": 82.0, "memory": 88.0,
        "ledger": {"asset_no": "ZC-SRV-0012", "owner": "王工", "usage": "数据库服务器",
                   "location": "A 机房 3 号机柜 U14"},
        "alerts": [("warning", "memory", 88.0, "内存使用率 88% 已达告警阈值"),
                   ("warning", "disk", 84.0, "数据盘使用率 84% 已达告警阈值")],
        "disk": 84.0, "temp": 41.2,
    },
    {
        "ip": "10.20.30.13", "name": "SRV-FILE-01", "model": "ProLiant DL380 Gen10",
        "vendor": "hpe", "vendor_display": "惠普",
        "version": "Windows Server 2016 Standard", "group": "文件服务器",
        "region": "机房B", "online": False, "cpu": None, "memory": None,
        "ledger": {"asset_no": "ZC-SRV-0013", "owner": "赵工", "usage": "文件服务器",
                   "location": "B 机房 1 号机柜 U20"},
        "alerts": [("critical", "reachability", None, "设备不可达：最近一次采集连接超时")],
        "disk": None, "temp": None,
    },
]

DEMO_SWITCHES = [
    {
        "ip": "10.20.10.2", "name": "CORE-SW-01", "model": "S12700E-8",
        "vendor": "huawei", "vendor_display": "华为", "role": "gateway",
        "version": "VRP (R) software, Version 5.170 (S12700 V200R019C10SPC500)",
        "group": "核心交换", "region": "机房A", "online": True, "cpu": 23.0, "memory": 46.0,
        "ledger": {"asset_no": "ZC-SW-0002", "owner": "李工", "usage": "核心交换机",
                   "location": "A 机房 1 号机柜 U1"},
        "error_ports": 0, "error_total": 0, "stp_state": "enabled",
        "stp_forward": 48, "stp_blocked": 2, "serial": "210235448510E100001",
        "echo": {
            "version": "Huawei Versatile Routing Platform Software\n"
                       "VRP (R) software, Version 5.170 (S12700 V200R019C10SPC500)\n"
                       "Copyright (C) 2012-2021 Huawei Technologies Co., Ltd.\n"
                       "HUAWEI S12700E-8 Routing Switch uptime is 411 days, 6 hours, 12 minutes",
            "serial": "Device Serial Number:210235448510E100001\n"
                      "Manufactured board information:\n  Board Name: S12700E-8 MPU\n"
                      "  Board Serial number:210235448510E100001",
            "cpu": "CPU Usage Stat. Cycle: 60 (Second)\nCPU Usage            : 23%  Max: 41%\n"
                   "CPU Usage Stat. Time : 2026-10-16  09:15:03\n"
                   "CPU utilization for five seconds: 23%: one minute: 18%: five minutes: 17%",
            "memory": "Memory utilization statistics at 2026-10-16 09:15:03\n"
                      "System Total Memory: 4096 MB\nTotal Used Memory: 1884 MB (46%)",
            "interfaces": "GigabitEthernet1/0/1 current state : UP\n"
                          "Line protocol current state : UP\n"
                          "  Errors: 0, Runts: 0, Giants: 0, CRC: 0, OverRun: 0\n"
                          "GigabitEthernet1/0/2 current state : UP\n"
                          "Line protocol current state : UP\n"
                          "  Errors: 0, Runts: 0, Giants: 0, CRC: 0, OverRun: 0\n"
                          "GigabitEthernet1/0/3 current state : DOWN\n"
                          "Line protocol current state : DOWN\n"
                          "  Errors: 0, Runts: 0, Giants: 0, CRC: 0, OverRun: 0",
            "stp": "MSTID   Port                        Role  STP State       Protection\n"
                   "0       GigabitEthernet1/0/1        ROOT  FORWARDING      NONE\n"
                   "0       GigabitEthernet1/0/2        DESI  FORWARDING      NONE\n"
                   "0       GigabitEthernet1/0/3        ALTE  DISCARDING      NONE",
            "alarm": "Alarm ID   Date                Time      Severity  Info",
            "config": "sysname CORE-SW-01\nstp mode mstp\nvlan batch 10 20 30 40\n"
                      "interface GigabitEthernet1/0/1\n description to-AGG-SW-01\n"
                      " port link-type trunk\n port trunk allow-pass vlan 10 20 30 40\n"
                      "return",
        },
    },
    {
        "ip": "10.20.10.3", "name": "AGG-SW-01", "model": "S5731-H48T4XC",
        "vendor": "huawei", "vendor_display": "华为", "role": "",
        "version": "VRP (R) software, Version 5.170 (S5731 V200R019C10SPC500)",
        "group": "汇聚交换", "region": "机房A", "online": True, "cpu": 47.0, "memory": 63.0,
        "ledger": {"asset_no": "ZC-SW-0003", "owner": "王工", "usage": "汇聚交换机",
                   "location": "A 机房 2 号机柜 U8"},
        "error_ports": 1, "error_total": 6, "stp_state": "enabled",
        "stp_forward": 30, "stp_blocked": 1, "serial": "210235448510E100002",
        "echo": {
            "version": "Huawei Versatile Routing Platform Software\n"
                       "VRP (R) software, Version 5.170 (S5731 V200R019C10SPC500)\n"
                       "HUAWEI S5731-H48T4XC Routing Switch uptime is 208 days, 2 hours",
            "serial": "Device Serial Number:210235448510E100002",
            "cpu": "CPU Usage Stat. Cycle: 60 (Second)\nCPU Usage            : 47%  Max: 88%\n"
                   "CPU Utilization for five seconds: 47%: one minute: 52%: five minutes: 44%",
            "memory": "Memory utilization statistics at 2026-10-16 09:15:04\n"
                      "System Total Memory: 2048 MB\nTotal Used Memory: 1290 MB (63%)",
            "interfaces": "GigabitEthernet0/0/1 current state : UP\n"
                          "Line protocol current state : UP\n"
                          "  Errors: 6, Runts: 0, Giants: 0, CRC: 6, OverRun: 0",
            "stp": "MSTID   Port                        Role  STP State       Protection\n"
                   "0       GigabitEthernet0/0/1        DESI  FORWARDING      NONE\n"
                   "0       GigabitEthernet0/0/24       ROOT  FORWARDING      NONE",
            "alarm": "Alarm ID   Date                Time      Severity  Info",
        },
    },
]


def _server_monitor(server: dict, when: str, salt: int = 10) -> dict:
    return {
        "id": _row_id(when, salt),
        "device_id": None, "device": server["name"], "device_ip": server["ip"],
        "sysname": server["name"], "serial": "",
        "version": server["version"], "cpu": server["cpu"], "memory": server["memory"],
        "ok": True, "error": "", "collected_at": when,
    }


def _server_inspection(server: dict, when: str, salt: int = 20) -> dict:
    return {
        "id": _row_id(when, salt),
        "run_id": "COLLECT-DEMO", "device_id": None, "device": server["name"],
        "device_ip": server["ip"], "cpu": server["cpu"], "memory": server["memory"],
        "stp_state": "", "stp_mode": "", "stp_forward": None, "stp_blocked": None,
        "error_ports": 0, "error_total": 0,
        "healthy": bool(server["online"]), "issues": "",
        "error": "" if server["online"] else "连接超时：Unable to connect to host",
        "inspected_at": when,
    }


def _server_echo(server: dict) -> str:
    """样例服务器的命令回显（仅用于示例报告；现场数据来自真实采集留档）。

    格式与 app/collect/server.py 一致：每个检查项一个分段，正文带 $ 命令行，
    报告直接按分段渲染成终端截图。
    """
    disk = "%.0f%%" % (server.get("disk") or 0)
    parts = {
        "os": ("$ uname -srm\nLinux 5.15.0-91-generic x86_64\n\n"
               "$ cat /etc/os-release\nPRETTY_NAME=\"%s\"\nID=%s\n\n"
               "$ hostname\n%s\n\n"
               "$ cat /sys/class/dmi/id/sys_vendor /sys/class/dmi/id/product_name "
               "/sys/class/dmi/id/product_serial\n%s\n%s\n%s"
               % (server["version"], "rhel" if "Red Hat" in server["version"] else "ubuntu",
                  server["name"].lower(), server["vendor_display"], server["model"],
                  "SN-" + server["name"].upper().replace("-", ""))),
        "cpu": ("$ top -bn1 | head -n 12\n"
                "top - 09:15:03 up 12 days,  3:21,  1 user,  load average: 0.42, 0.51, 0.48\n"
                "Tasks: 231 total,   1 running, 230 sleeping\n"
                "%%Cpu(s):  %.1f us,  1.0 sy,  0.0 ni, %.1f id,  0.2 wa"
                % ((server["cpu"] or 0) * 0.6, 100 - (server["cpu"] or 0))),
        "memory": ("$ free -m\n"
                   "               total        used        free      shared  buff/cache   available\n"
                   "Mem:           65536       %.0f       10000         123       20000       33000\n"
                   "Swap:           8191           0        8191"
                   % (65536 * (server["memory"] or 0) / 100.0)),
        "disk": ("$ df -hT -x tmpfs -x devtmpfs -x overlay\n"
                 "Filesystem     Type  Size  Used Avail Use%% Mounted on\n"
                 "/dev/sda2      ext4  200G  120G   70G  %s /\n"
                 "/dev/sdb1      xfs   2.0T  1.2T  700G  63%% /data" % disk),
        "net": ("$ ip -br addr\n"
                "lo               UNKNOWN        127.0.0.1/8\n"
                "ens192           UP             %s/24" % server["ip"]),
        "service": ("$ systemctl --failed --no-pager\n"
                    "  UNIT  LOAD  ACTIVE SUB  DESCRIPTION\n"
                    "0 loaded units listed."),
        "log": ("$ journalctl -p err -n 20 --no-pager\n"
                "-- Logs begin at Mon 2026-09-01 00:00:00 CST, end at %s --\n"
                "No entries" % _stamp(0.2)),
        "temp": ("$ for f in /sys/class/thermal/thermal_zone*/temp; do "
                  "test -r \"$f\" && echo \"$f $(cat $f)\"; done\n"
                  "/sys/class/thermal/thermal_zone0/temp %d"
                  % int((server.get("temp") or 0) * 1000)),
        "backup": ("$ ls -lt /var/backups | head -n 12\n"
                   "-rw-r--r-- 1 root root 1288490188 %s backup_%s.tar.gz"
                   % (_stamp(1.0), server["name"].lower())),
    }
    return "\n".join("──── %s ────\n%s" % (key, body) for key, body in parts.items())


def seed_demo(store) -> dict:
    """往（临时）库里补样例服务器与样例交换机，返回写入统计。"""
    from app import normalize as nz   # noqa: F401   （仅做导入可用性校验）
    settings = {"data_source": "local", "org_name": "林鉴知微技术服务股份有限公司",
                "site_name": "林鉴知微平台 | LinScopePlatform", "period_days": "7"}
    store.save_settings(settings)

    known = {row.get("ip") for row in store.devices()}
    added = {"servers": 0, "switches": 0, "logs": 0}

    def upsert_device(device):
        store.device_upsert(device)
        if device.get("ledger"):
            store.ledger_save(device["ip"], device["ledger"])

    for index, server in enumerate(DEMO_SERVERS):
        if server["ip"] in known:
            continue
        upsert_device({
            "ip": server["ip"], "name": server["name"], "vendor": server["vendor"],
            "vendor_display": server["vendor_display"], "model": server["model"],
            "version": server["version"], "group": server["group"],
            "region": server["region"], "online": server["online"], "port": 22,
            "role": "", "source": "local",
            "last_online_at": _stamp(0.1 if server["online"] else 3.0),
        })
        added["servers"] += 1
        stamps = [_stamp(0.2 + i * 0.5) for i in range(6)]
        device_id = (store.device_get(server["ip"]) or {}).get("id")
        store.save_monitors([_server_monitor(server, when, 10 + index)
                             for when in stamps])
        # 磁盘 / 温度写进 metrics（服务器健康页与报告的「运行状态检查」都读这张表）
        metric_rows = []
        for offset, when in enumerate(stamps):
            if server.get("disk") is not None:
                metric_rows.append({
                    "id": _row_id(when, 80 + index * 10 + offset),
                    "device_id": device_id, "device": server["name"],
                    "device_ip": server["ip"], "metric": "disk",
                    "label": "磁盘使用率", "value": server["disk"], "unit": "%",
                    "source": "collect", "collected_at": when})
            if server.get("temp") is not None:
                metric_rows.append({
                    "id": _row_id(when, 81 + index * 10 + offset),
                    "device_id": device_id, "device": server["name"],
                    "device_ip": server["ip"], "metric": "temp",
                    "label": "机箱温度", "value": server["temp"], "unit": "℃",
                    "source": "collect", "collected_at": when})
        if metric_rows:
            store.save_metrics(metric_rows)
        rows = []
        for offset, when in enumerate(stamps):
            row = _server_inspection(server, when, 20 + index)
            row["cpu"] = None if server["cpu"] is None else server["cpu"] + (offset % 3) - 1
            row["memory"] = None if server["memory"] is None else server["memory"] + (offset % 2)
            rows.append(row)
        store.save_inspections(rows)
        alerts = []
        for offset, (severity, metric, value, content) in enumerate(server["alerts"]):
            alerts.append({
                "id": _row_id(_stamp(0.3), 30 + index * 5 + offset),
                "source": "local", "source_display": "本平台采集判定",
                "severity": severity, "status": "open",
                "device": server["name"], "device_ip": server["ip"],
                "rule": "threshold", "metric": metric, "value": value,
                "content": content, "triggered_at": _stamp(0.3),
            })
        if alerts:
            store.save_alerts(alerts)
        if server["online"]:
            store.save_backups([{
                "name": "backup_%s_%s.cfg" % (server["ip"].replace(".", "_"), "20261016"),
                "device_ip": server["ip"], "size": 12048, "mtime": _stamp(1.0),
            }])
            store.collect_log(0, server["ip"], server["name"], True, "", 812,
                              "systeminfo ; df -h ; free -m ; ip addr",
                              "CPU %.0f%% · 内存 %.0f%% · 磁盘 %.0f%% · 告警 %d"
                              % (server["cpu"] or 0, server["memory"] or 0,
                                 server["disk"] or 0, len(alerts)),
                              _server_echo(server))
            added["logs"] += 1
        else:
            store.collect_log(0, server["ip"], server["name"], False,
                              "连接超时：Unable to connect to host", 0, "", "")

    existing_switches = [row for row in store.devices()
                         if (row.get("vendor") or "").lower() == "huawei"
                         and not any(h in (row.get("model") or "").lower()
                                     for h in ("poweredge", "thinksystem", "proliant"))]
    if not existing_switches:
        for index, switch in enumerate(DEMO_SWITCHES):
            if switch["ip"] in known:
                continue
            upsert_device({
                "ip": switch["ip"], "name": switch["name"], "vendor": switch["vendor"],
                "vendor_display": switch["vendor_display"], "model": switch["model"],
                "version": switch["version"], "serial": switch["serial"],
                "role": switch["role"], "group": switch["group"],
                "region": switch["region"], "online": switch["online"], "port": 22,
                "source": "local", "last_online_at": _stamp(0.1),
            })
            added["switches"] += 1
            stamps = [_stamp(0.2 + i * 0.5) for i in range(6)]
            store.save_inspections([{
                "id": _row_id(when, 60 + index),
                "run_id": "COLLECT-DEMO", "device_id": None, "device": switch["name"],
                "device_ip": switch["ip"], "cpu": switch["cpu"] + (i % 3) - 1,
                "memory": switch["memory"] + (i % 2), "stp_state": switch["stp_state"],
                "stp_mode": "MSTP", "stp_forward": switch["stp_forward"],
                "stp_blocked": switch["stp_blocked"],
                "error_ports": switch["error_ports"], "error_total": switch["error_total"],
                "healthy": True, "issues": "", "error": "", "inspected_at": when,
            } for i, when in enumerate(stamps)])
            store.save_monitors([{
                "id": _row_id(when, 70 + index),
                "device_id": None, "device": switch["name"], "device_ip": switch["ip"],
                "sysname": switch["name"], "serial": switch["serial"],
                "version": switch["version"], "cpu": switch["cpu"],
                "memory": switch["memory"], "ok": True, "error": "",
                "collected_at": when,
            } for when in stamps])
            store.save_backups([{
                "name": "backup_%s_20261016.cfg" % switch["ip"].replace(".", "_"),
                "device_ip": switch["ip"], "size": 18624, "mtime": _stamp(1.0),
            }])
            store.collect_log(0, switch["ip"], switch["name"], True, "", 175,
                              "screen-length 0 temporary ; display version ; "
                              "display device manuinfo ; display cpu-usage ; "
                              "display memory-usage ; display interface ; "
                              "display stp brief ; display alarm",
                              "CPU %.0f%% · 内存 %.0f%% · 端口 down 1 · 错包口 %d · 告警 0"
                              % (switch["cpu"], switch["memory"], switch["error_ports"]),
                              "\n".join("──── %s ────\n%s" % (key, body)
                                        for key, body in switch["echo"].items()))
            added["logs"] += 1
    return added


# ------------------------------------------------------------------ 主流程
def _source_db(db: str | None) -> str:
    """源数据库路径：--db 优先，其次 NIP_DATA_DIR，最后 backend/data 下的默认库。"""
    if db:
        return os.path.abspath(db)
    data_dir = os.environ.get("NIP_DATA_DIR") or os.path.join(BACKEND_DIR, "data")
    return os.path.join(data_dir, "netinspect.sqlite3")


def _prepare_env(demo: bool, db: str | None) -> str:
    """把运行环境指到目标库上（必须在 import app.* 之前做完）。

    返回实际使用的数据库路径。
    """
    source = _source_db(db)
    if not demo:
        if db or os.environ.get("NIP_DATA_DIR"):
            os.environ["NIP_DATA_DIR"] = os.path.dirname(source)
            os.environ.setdefault("DATA_SOURCE", "local")
        return source
    tmpdir = tempfile.mkdtemp(prefix="netinspect-report-")
    target = os.path.join(tmpdir, "netinspect.sqlite3")
    if os.path.exists(source):
        src = sqlite3.connect(source)
        dst = sqlite3.connect(target)
        with dst:
            src.backup(dst)                 # 用 SQLite 备份 API，WAL 里的数据也一并带过来
        src.close()
        dst.close()
    os.environ["NIP_DATA_DIR"] = tmpdir
    os.environ["DATA_SOURCE"] = "local"
    print("已把现场库复制到临时目录：%s" % target)
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成服务器 / 交换机健康性检查报告（Word / PDF）")
    parser.add_argument("--kind", default="both",
                        choices=["server", "switch", "both"],
                        help="生成哪一类报告（默认 both）")
    parser.add_argument("--out", default="reports-out", help="输出目录")
    parser.add_argument("--format", default="both", choices=["docx", "pdf", "both"])
    parser.add_argument("--hours", type=int, default=24 * 7, help="统计区间（小时）")
    parser.add_argument("--device", default="", help="只出某一台设备（设备 id 或 IP）")
    parser.add_argument("--customer", default="", help="封面上的客户名（默认 XXX公司）")
    parser.add_argument("--demo", action="store_true",
                        help="使用测试数据：拷贝一份库到临时目录并补样例设备")
    parser.add_argument("--db", default="", help="指定源数据库（默认 backend/data 下的库）")
    parser.add_argument("--dump-images", action="store_true",
                        help="把报告里的截图 / 图表单独导出到 <out>/images")
    args = parser.parse_args(argv)

    target = _prepare_env(args.demo, args.db or None)

    from app import config, service          # noqa: E402
    from app.store import get_store          # noqa: E402
    from app import docreport                # noqa: E402

    store = get_store()
    if args.demo:
        added = seed_demo(store)
        print("测试数据已写入临时库 %s：服务器 %d 台、交换机 %d 台、采集日志 %d 条"
              % (config.DB_PATH, added["servers"], added["switches"], added["logs"]))
    service.cache_clear()

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    image_dir = os.path.join(out_dir, "images")
    if args.dump_images:
        os.makedirs(image_dir, exist_ok=True)

    kinds = ["server", "switch"] if args.kind == "both" else [args.kind]
    formats = ["docx", "pdf"] if args.format == "both" else [args.format]
    params = {"hours": args.hours, "device": args.device}
    if args.customer:
        params["customer"] = args.customer

    written = []
    for kind in kinds:
        for fmt in formats:
            try:
                filename, payload, stats = docreport.build(kind, params, fmt)
            except Exception as exc:                        # noqa: BLE001
                print("！！%s 报告（%s）生成失败：%s\n"
                      "  提示：若库里还没有该类型设备，可先用 --demo 出一份样例报告核对版式。"
                      % (kind, fmt, exc))
                raise SystemExit(1)
            path = os.path.join(out_dir, filename)
            with open(path, "wb") as handle:
                handle.write(payload)
            written.append((path, len(payload), stats))
            print("已生成 %-58s %8.1f KB  设备 %d 台 · 表格 %d · 截图 %d"
                  % (os.path.basename(path), len(payload) / 1024.0,
                     stats.get("devices") or 0, stats.get("tables") or 0,
                     stats.get("images") or 0))
            if args.dump_images:
                _dump_images(kind, params, image_dir)
    print("\n共 %d 份报告，输出目录：%s" % (len(written), out_dir))
    return 0


def _safe_name(text: str) -> str:
    """把标题里的非法文件名字符换掉（Windows 下 : / \\ * ? " < > | 都不能进文件名）。"""
    keep = []
    for ch in str(text):
        keep.append("_" if ch in '\\/:*?"<>|' else ch)
    return "".join(keep).replace(" ", "")


def _dump_images(kind: str, params: dict, image_dir: str) -> None:
    """把报告里的图片块单独落盘（截图与图表各存一份，便于插进其它文档）。"""
    from app.docreport import content
    report = content.build(kind, params)
    index = 0
    for block_kind, payload in report.blocks:
        if block_kind != "img":
            continue
        index += 1
        caption = _safe_name(payload.get("caption") or "image")
        name = "%s-%02d-%s.png" % (kind, index, caption[:60] or "image")
        with open(os.path.join(image_dir, name), "wb") as handle:
            handle.write(payload["data"])
    print("  截图 / 图表已导出到 %s（%d 张）" % (image_dir, index))


if __name__ == "__main__":
    raise SystemExit(main())
