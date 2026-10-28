# -*- coding: utf-8 -*-
"""写入 10 台演示设备（覆盖全部设备类型）+ 6 轮巡检 + 告警 / 备份 / 采集回显。

用途：在一套干净的部署上快速造出一批可查询、可操作、可出报告的演示数据。

* 设备全部使用 10.20.x.x 网段，名称固定；按 IP 先删后写，可重复执行；
* 交换机/路由器/防火墙/AC 走 VRP 回显，服务器走 Linux / Windows 回显；
* 每台 6 轮巡检（含 CPU/内存走势）、监控、指标、告警、备份与一条采集日志；
* 一条"离线"设备用于演示采集失败与"未采集"口径。

用法（部署目录内）：
    backend/.venv/bin/python backend/tools/seed_demo_devices.py
    backend/.venv/bin/python backend/tools/seed_demo_devices.py --clear
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import remote, service          # noqa: E402
from app.store import get_store          # noqa: E402

DEMO = [
    dict(ip="10.20.10.2", name="CORE-SW-01", vendor="huawei", vendor_display="华为",
         model="S12700E-8", version="VRP (R) software, Version 5.170 (S12700 V200R019C10SPC500)",
         serial="210235448510E100001", role="gateway", kind="switch",
         group="核心交换", region="A机房", usage="核心交换机", location="A机房 1号机柜 U1",
         owner="张工", asset="ZC-SW-0002", online=True,
         cpu=23, mem=46, errors=0, err_ports=0, stp="enabled", fwd=48, blocked=2,
         uptime="411 days, 6 hours, 12 minutes", alarms=[], backups=3,
         down_ports=[], alerts=[]),
    dict(ip="10.20.10.3", name="AGG-SW-01", vendor="huawei", vendor_display="华为",
         model="S5731-H48T4XC", version="VRP (R) software, Version 5.170 (S5731 V200R019C10SPC500)",
         serial="210235448510E100002", role="", kind="switch",
         group="汇聚交换", region="A机房", usage="汇聚交换机", location="A机房 2号机柜 U8",
         owner="王工", asset="ZC-SW-0003", online=True,
         cpu=47, mem=63, errors=6, err_ports=1, stp="enabled", fwd=30, blocked=1,
         uptime="208 days, 2 hours", alarms=[], backups=2,
         down_ports=[], alerts=[("warning", "if_errors", "端口 GigabitEthernet0/0/24 存在错误包（CRC 6 / Errors 0）", 6)]),
    dict(ip="10.20.10.4", name="ACC-SW-01", vendor="huawei", vendor_display="华为",
         model="S5720-28X-SI-AC", version="VRP (R) software, Version 5.170 (S5720 V200R019C10SPC500)",
         serial="210235448510E100003", role="access", kind="switch",
         group="接入交换", region="B机房", usage="接入交换机", location="B机房 1号机柜 U20",
         owner="李工", asset="ZC-SW-0004", online=True,
         cpu=77, mem=99, errors=33, err_ports=1, stp="enabled", fwd=2, blocked=1,
         uptime="130 days, 15 hours, 28 minutes", alarms=[],
         backups=1, down_ports=["GigabitEthernet0/0/2"],
         alerts=[("major", "port_down", "端口 GigabitEthernet0/0/2 处于 down 状态（无描述）", None),
                 ("warning", "if_errors", "端口 GigabitEthernet0/0/3 存在错误包（CRC 21 / Errors 12）", 33)]),
    dict(ip="10.20.10.5", name="ACC-SW-02", vendor="huawei", vendor_display="华为",
         model="S5735-L24T4S-A", version="VRP (R) software, Version 5.170 (S5735 V200R021C10SPC600)",
         serial="210235448510E100004", role="access", kind="switch",
         group="接入交换", region="B机房", usage="接入交换机", location="B机房 2号机柜 U12",
         owner="赵工", asset="ZC-SW-0005", online=False,
         cpu=None, mem=None, errors=0, err_ports=0, stp="unknown", fwd=None, blocked=None,
         uptime="", alarms=[], backups=0, down_ports=[],
         alerts=[("critical", "reachability", "设备不可达：最近一次采集连接超时", None)]),
    dict(ip="10.20.20.1", name="RT-WAN-01", vendor="huawei", vendor_display="华为",
         model="AR6300 Router", version="VRP (R) software, Version 8.180 (AR6300 V300R019C10SPC300)",
         serial="210235448510E200001", role="", kind="switch",
         group="出口路由", region="A机房", usage="出口路由器", location="A机房 3号机柜 U2",
         owner="张工", asset="ZC-RT-0001", online=True,
         cpu=35, mem=41, errors=0, err_ports=0, stp="enabled", fwd=6, blocked=0,
         uptime="356 days, 4 hours", alarms=[], backups=2, down_ports=[], alerts=[]),
    dict(ip="10.20.30.1", name="FW-DMZ-01", vendor="huawei", vendor_display="华为",
         model="USG6650E", version="VRP (R) software, Version 5.170 (USG6650E V500R005C20SPC300)",
         serial="210235448510E300001", role="", kind="switch",
         group="边界安全", region="A机房", usage="边界防火墙（DMZ）", location="A机房 3号机柜 U6",
         owner="钱工", asset="ZC-FW-0001", online=True,
         cpu=61, mem=58, errors=0, err_ports=0, stp="unknown", fwd=None, blocked=None,
         uptime="88 days, 9 hours",
         alarms=[("Major", "2026-10-17 03:22:41", "The session table usage reached 82%")],
         backups=2, down_ports=[],
         alerts=[("major", "device_alarm", "设备告警[Major] The session table usage reached 82%", None)]),
    dict(ip="10.20.40.1", name="WAC-01", vendor="huawei", vendor_display="华为",
         model="AC6605", version="VRP (R) software, Version 5.170 (AC6605 V200R019C10SPC500)",
         serial="210235448510E400001", role="", kind="switch",
         group="无线网络", region="A机房", usage="无线控制器", location="A机房 2号机柜 U18",
         owner="孙工", asset="ZC-AC-0001", online=True,
         cpu=33, mem=39, errors=0, err_ports=0, stp="unknown", fwd=None, blocked=None,
         uptime="201 days, 2 hours", alarms=[], backups=1, down_ports=[], alerts=[]),
    dict(ip="10.20.50.11", name="SRV-APP-01", vendor="dell", vendor_display="戴尔",
         model="PowerEdge R750", version="Ubuntu 22.04.3 LTS",
         serial="ABC1234", role="", kind="server",
         group="业务服务器", region="A机房", usage="应用服务器", location="A机房 5号机柜 U12",
         owner="李工", asset="ZC-SRV-0011", online=True,
         cpu=34, mem=61, disk=72, temp=38.5, failed=0, os_name="Ubuntu 22.04.3 LTS",
         alerts=[], backups=1),
    dict(ip="10.20.50.12", name="SRV-DB-01", vendor="lenovo", vendor_display="联想",
         model="ThinkSystem SR650", version="Red Hat Enterprise Linux 8.6",
         serial="SN-SRVDB01", role="", kind="server",
         group="数据库服务器", region="A机房", usage="数据库服务器", location="A机房 5号机柜 U14",
         owner="王工", asset="ZC-SRV-0012", online=True,
         cpu=82, mem=88, disk=84, temp=41.2, failed=1, os_name="Red Hat Enterprise Linux 8.6",
         alerts=[("major", "cpu_high", "CPU 使用率 82% 偏高", 82),
                 ("major", "memory_high", "内存使用率 88% 偏高", 88),
                 ("warning", "disk_high", "磁盘使用率 84% 偏高", 84)],
         backups=1),
    dict(ip="10.20.50.21", name="SRV-WIN-01", vendor="hpe", vendor_display="惠普",
         model="ProLiant DL380 Gen10", version="Windows Server 2019 Datacenter",
         serial="WIN-SRV21", role="", kind="server",
         group="文件服务器", region="B机房", usage="文件服务器", location="B机房 2号机柜 U8",
         owner="赵工", asset="ZC-SRV-0021", online=True,
         cpu=28, mem=52, disk=63, temp=None, failed=0, os_name="Windows Server 2019 Datacenter",
         alerts=[], backups=1),
]


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _vary(base, index: int, delta: int = 6):
    if base is None:
        return None
    return max(1, min(99, base + (index % 3 - 1) * delta))


def _block(key: str, body: str) -> str:
    return "──── %s ────\n%s" % (key, (body or "").strip())


def switch_echo(d: dict) -> str:
    name, model, ver = d["name"], d["model"], d["version"]
    ports = [
        ("GigabitEthernet0/0/1", "UP", "to-%s" % ("CORE-SW-01" if name != "CORE-SW-01" else "AGG-SW-01"), 0, 0),
        ("GigabitEthernet0/0/2", "DOWN" if "GigabitEthernet0/0/2" in d.get("down_ports", []) else "UP", "", 0, 0),
        ("GigabitEthernet0/0/3", "UP", "to-access", (21 if d.get("err_ports") else 0), (12 if d.get("err_ports") else 0)),
        ("GigabitEthernet0/0/24", "UP", "uplink", 0, 0),
    ]
    intf_lines = []
    for port, state, desc, crc, errors in ports:
        intf_lines.append(
            "%s current state : %s\nLine protocol current state : %s\nDescription:%s\n"
            "Input bandwidth utilization  :    1%%\nOutput bandwidth utilization :    2%%\n"
            "  Errors: %d, Runts: 0, Giants: 0, CRC: %d, OverRun: 0"
            % (port, state, state, desc, errors, crc))
    stp_lines = ["MSTID   Port                        Role  STP State       Protection"]
    for index in range(int(d.get("fwd") or 2)):
        stp_lines.append("0       GigabitEthernet0/0/%d        DESI  FORWARDING      NONE" % (index + 1))
    for index in range(int(d.get("blocked") or 0)):
        stp_lines.append("0       GigabitEthernet0/0/%d        ALTE  DISCARDING      NONE" % (48 - index))
    alarm_lines = ["Alarm ID   Date                Time      Severity  Info"]
    for alarm in d.get("alarms", []):
        sev, when, info = alarm
        date, clock = (when.split(" ") + ["00:00:00"])[:2]
        alarm_lines.append("0x%s %s %s %-9s %s" % ("d916f021", date, clock, sev, info))
    return "\n\n".join([
        _block("version", "Huawei Versatile Routing Platform Software\n%s\n"
                          "HUAWEI %s Routing Switch uptime is %s" % (ver, model, d["uptime"])),
        _block("serial", "Device Serial Number:%s\nManufactured board information:\n"
                         "  Board Name: %s\n  Board Serial number:%s" % (d["serial"], model, d["serial"])),
        _block("cpu", "CPU Usage Stat. Cycle: 60 (Second)\nCPU Usage            : %.0f%%  Max: %.0f%%\n"
                      "CPU utilization for five seconds: %.0f%%: one minute: %d%%: five minutes: %d%%"
                      % (d["cpu"], min(99, d["cpu"] + 15), d["cpu"], max(1, d["cpu"] - 8), max(1, d["cpu"] - 12))),
        _block("memory", "Memory utilization statistics\nSystem Total Memory: 4096 MB\n"
                         "Total Used Memory: %d MB (%.0f%%)" % (4096 * d["mem"] / 100, d["mem"])),
        _block("interfaces", "\n\n".join(intf_lines)),
        _block("stp", "\n".join(stp_lines)),
        _block("lldp", "Local Intf          Neighbor Dev             Neighbor Intf       Exptime(s)\n"
                       "GE0/0/1             %-24s GE0/0/2             121\n"
                       "GE0/0/24            %-24s GE0/0/24            118"
                       % ("CORE-SW-01" if name != "CORE-SW-01" else "AGG-SW-01", "ACC-SW-01")),
        _block("alarm", "\n".join(alarm_lines)),
        _block("config", "sysname %s\nstp mode mstp\nvlan batch 10 20 30 40\n"
                         "interface GigabitEthernet0/0/1\n description to-uplink\n"
                         " port link-type trunk\n port trunk allow-pass vlan 10 20 30 40\nreturn" % name),
    ])[:8000]


def server_echo(d: dict) -> str:
    win = d["version"].startswith("Windows")
    prompt = "PS C:\\>" if win else "$"
    if win:
        os_body = ("PS C:\\> Get-CimInstance Win32_OperatingSystem | ForEach-Object { "
                   "'Caption ' + $_.Caption; 'Version ' + $_.Version }\n"
                   "Caption %s\nVersion 10.0.17763" % d["version"])
        cpu_body = ("PS C:\\> Get-CimInstance Win32_Processor\nName Intel(R) Xeon(R) Gold 6338\n"
                    "LoadPercentage %.0f\nNumberOfLogicalProcessors 16" % d["cpu"])
        mem_body = ("PS C:\\> Get-CimInstance Win32_OperatingSystem\n"
                    "TotalVisibleMemorySize 65345876\nFreePhysicalMemory %d"
                    % int(65345876 * (100 - d["mem"]) / 100))
        disk_body = ("PS C:\\> Get-CimInstance Win32_LogicalDisk\nC: 499000000000 %d"
                     % int(499000000000 * (100 - d["disk"]) / 100))
        net_body = ("PS C:\\> Get-NetIPAddress -AddressFamily IPv4\nEthernet0 %s/24" % d["ip"])
        service_body = "PS C:\\> Get-Service | Where-Object { $_.Status -ne 'Running' }\n(none)"
        log_body = ("PS C:\\> Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2} -MaxEvents 20\n"
                    "(no error events)")
        temp_body = ""
        backup_body = ("PS C:\\> Get-ChildItem C:\\Backup | Select-Object -First 3\n"
                       "backup_20261016.zip 1200000 2026-10-16 02:00:00")
    else:
        os_body = ("$ uname -srm\nLinux 5.15.0-91-generic x86_64\n\n$ cat /etc/os-release\n"
                   "PRETTY_NAME=\"%s\"\nID=ubuntu\n\n$ hostname\n%s\n\n"
                   "$ cat /sys/class/dmi/id/sys_vendor /sys/class/dmi/id/product_name "
                   "/sys/class/dmi/id/product_serial\n%s\n%s\n%s"
                   % (d["version"], d["name"].lower(), d["vendor_display"], d["model"], d["serial"]))
        cpu_body = ("$ top -bn1 | head -n 12\ntop - 09:15:03 up 12 days, 3:21\n"
                    "%%Cpu(s): %.1f us, 1.0 sy, 0.0 ni, %.1f id, 0.2 wa"
                    % (d["cpu"] * 0.6, 100 - d["cpu"]))
        mem_body = ("$ free -m\n               total        used        free      shared  buff/cache   available\n"
                    "Mem:           65536       %d       10000         123       20000       33000\n"
                    "Swap:           8191           0        8191" % int(65536 * d["mem"] / 100))
        disk_body = ("$ df -hT -x tmpfs\nFilesystem     Type  Size  Used Avail Use%% Mounted on\n"
                     "/dev/sda2      ext4  200G  120G   70G  %d%% /\n"
                     "/dev/sdb1      xfs   2.0T  1.2T  700G  63%% /data" % d["disk"])
        net_body = ("$ ip -br addr\nlo               UNKNOWN        127.0.0.1/8\n"
                    "ens192           UP             %s/24" % d["ip"])
        service_body = ("$ systemctl --failed --no-pager\n  UNIT LOAD ACTIVE SUB DESCRIPTION\n"
                        + ("db.service loaded failed failed Database Service" if d.get("failed") else "0 loaded units listed."))
        log_body = ("$ journalctl -p err -n 20 --no-pager\n-- Logs begin at 2026-09-01 --\n"
                    + ("Oct 17 03:22:41 srv kernel: EXT4-fs error on sda2" if d.get("failed") else "No entries"))
        temp_body = ("$ for f in /sys/class/thermal/thermal_zone*/temp; do echo \"$f $(cat $f)\"; done\n"
                     "/sys/class/thermal/thermal_zone0/temp %d" % int((d.get("temp") or 40) * 1000))
        backup_body = ("$ ls -lt /var/backups | head -n 3\n"
                       "-rw-r--r-- 1 root root 1288490188 2026-10-16 02:00 backup_%s.tar.gz" % d["name"].lower())
    parts = [("os", os_body), ("cpu", cpu_body), ("memory", mem_body), ("disk", disk_body),
             ("net", net_body), ("service", service_body), ("log", log_body),
             ("temp", temp_body), ("backup", backup_body)]
    return "\n\n".join(_block(k, v) for k, v in parts if (v or "").strip())[:8000]


def wipe(store, ip: str) -> None:
    with store.connect() as conn:
        for table in ("inspections", "monitors", "metrics", "alerts", "backups",
                      "collect_logs", "ledger"):
            conn.execute("DELETE FROM %s WHERE device_ip=?" % table, (ip,))
        conn.execute("DELETE FROM credentials WHERE ip=?", (ip,))
        conn.execute("DELETE FROM devices WHERE ip=?", (ip,))


def seed(clear: bool = False) -> dict:
    store = get_store()
    now = datetime.now()
    added = 0
    run_id = store.collect_run_start("manual")
    ok = failed = 0
    for index, d in enumerate(DEMO):
        ip = d["ip"]
        wipe(store, ip)
        if clear:
            continue
        store.device_upsert({
            "ip": ip, "name": d["name"], "vendor": d["vendor"],
            "vendor_display": d["vendor_display"], "model": d["model"],
            "version": d["version"], "serial": d["serial"], "role": d["role"],
            "group": d["group"], "region": d["region"],
            "online": d["online"], "port": 22, "source": "local",
            "last_online_at": _stamp(now - timedelta(minutes=5 if d["online"] else 320)),
        })
        device = store.device_get(ip)
        device_id = device.get("id")
        store.ledger_save(ip, {
            "device_id": device_id, "device_name": d["name"], "asset_no": d["asset"],
            "owner": d["owner"], "usage": d["usage"], "location": d["location"],
            "note": "演示数据",
        })
        with store.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO credentials(ip, device_name, port, username, auth,"
                " secret_enc, key_enc, key_pass_enc, vendor, note, updated_at, updated_by)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (ip, d["name"], 22, "netadmin", "password",
                 remote.encrypt("Demo@12345"), "", "", d["vendor"],
                 "演示凭据（设备不可达时采集会失败）", _stamp(now), "admin"))
        added += 1

        # ---- 6 轮巡检 / 监控 / 指标
        rounds = 6 if d["online"] else 3
        for r in range(rounds):
            when = _stamp(now - timedelta(hours=(rounds - 1 - r) * 6))
            cpu = _vary(d.get("cpu"), r)
            mem = _vary(d.get("mem"), r)
            healthy = bool(d["online"]) and (cpu or 0) < 90 and (mem or 0) < 90
            issues = ""
            if d["kind"] == "switch":
                if (cpu or 0) >= 80:
                    issues = "CPU 使用率 %.0f%% 偏高" % cpu
                if (mem or 0) >= 80:
                    issues = (issues + "；" if issues else "") + "内存使用率 %.0f%% 偏高" % mem
                if d.get("errors"):
                    issues = (issues + "；" if issues else "") + "%d 个接口存在错误包" % d["err_ports"]
                if d.get("down_ports"):
                    issues = (issues + "；" if issues else "") + "端口 down：%s" % "、".join(d["down_ports"])
                if d["online"] is False:
                    issues = "设备不可达"
                ports = [{"name": "GigabitEthernet0/0/%d" % (i + 1), "up": True,
                          "description": ""} for i in range(4)]
                for port in ports:
                    if port["name"] in (d.get("down_ports") or []):
                        port["up"] = False
                store.save_inspections([{
                    "id": service_next_id(), "run_id": "DEMO-%d" % run_id,
                    "device_id": device_id, "device": d["name"], "device_ip": ip,
                    "cpu": cpu, "memory": mem, "stp_state": d["stp"], "stp_mode": "MSTP",
                    "stp_forward": d["fwd"], "stp_blocked": d["blocked"],
                    "error_ports": d["err_ports"], "error_total": d["errors"],
                    "healthy": healthy, "issues": issues, "error": "",
                    "inspected_at": when, "ports": ports, "uptime_text": d["uptime"],
                    "uptime_seconds": 411 * 86400, "lldp": [],
                }])
            else:
                if (cpu or 0) >= 80:
                    issues = "CPU 使用率 %.0f%% 偏高" % cpu
                if (mem or 0) >= 80:
                    issues = (issues + "；" if issues else "") + "内存使用率 %.0f%% 偏高" % mem
                if (d.get("disk") or 0) >= 85:
                    issues = (issues + "；" if issues else "") + "磁盘使用率 %.0f%% 偏高" % d["disk"]
                store.save_inspections([{
                    "id": service_next_id(), "run_id": "DEMO-%d" % run_id,
                    "device_id": device_id, "device": d["name"], "device_ip": ip,
                    "cpu": cpu, "memory": mem, "stp_state": "", "stp_mode": "",
                    "stp_forward": None, "stp_blocked": None,
                    "error_ports": 0, "error_total": 0,
                    "healthy": not issues, "issues": issues, "error": "",
                    "inspected_at": when, "ports": [], "uptime_text": "12 days",
                    "uptime_seconds": 12 * 86400,
                }])
                store.save_metrics([
                    {"id": service_next_id(), "device_id": device_id, "device": d["name"],
                     "device_ip": ip, "metric": "disk", "label": "磁盘使用率",
                     "value": d["disk"], "unit": "%", "source": "collect",
                     "collected_at": when},
                ] + ([{"id": service_next_id(), "device_id": device_id, "device": d["name"],
                       "device_ip": ip, "metric": "temp", "label": "机箱温度",
                       "value": d["temp"], "unit": "℃", "source": "collect",
                       "collected_at": when}] if d.get("temp") is not None else [])
                  + ([{"id": service_next_id(), "device_id": device_id, "device": d["name"],
                       "device_ip": ip, "metric": "failed_services", "label": "未运行服务",
                       "value": d.get("failed") or 0, "unit": "个", "source": "collect",
                       "collected_at": when}] if d.get("failed") is not None else []))
            store.save_monitors([{
                "id": service_next_id(), "device_id": device_id, "device": d["name"],
                "device_ip": ip, "sysname": d["name"], "serial": d["serial"],
                "version": d["version"], "cpu": cpu, "memory": mem,
                "ok": True, "error": "", "collected_at": when,
            }])

        # ---- 告警
        rows = []
        for severity, metric, content, value in d.get("alerts", []):
            rows.append({
                "id": service_next_id(), "source": "monitor", "source_display": "本平台采集",
                "severity": severity, "status": "new", "device": d["name"],
                "device_ip": ip, "rule": "本平台采集判定", "metric": metric,
                "value": value, "content": content, "dedupe_key": metric,
                "triggered_at": _stamp(now - timedelta(hours=2)),
            })
        if rows:
            store.save_alerts(rows)

        # ---- 配置备份
        if d.get("backups"):
            store.save_backups([{
                "name": "backup_%s_20261016.cfg" % ip.replace(".", "_"),
                "device_ip": ip, "size": 18624,
                "mtime": _stamp(now - timedelta(days=1)),
            }])

        # ---- 采集日志（带回显，报告截图用）
        if d["online"]:
            echo = switch_echo(d) if d["kind"] == "switch" else server_echo(d)
            commands = ("display version ; display device manuinfo ; display cpu-usage ; "
                        "display memory-usage ; display interface ; display stp brief ; "
                        "display lldp neighbor ; display alarm"
                        if d["kind"] == "switch" else
                        "uname -srm ; cat /etc/os-release ; hostname ; uptime ; top -bn1 ; "
                        "free -m ; df -hT ; ip -br addr ; systemctl --failed ; journalctl -p err")
            summary = ("CPU %.0f%% · 内存 %.0f%% · 端口 down %d · 错包口 %d · 告警 %d"
                       % (d.get("cpu") or 0, d.get("mem") or 0,
                          len(d.get("down_ports") or []), d.get("err_ports") or 0,
                          len(d.get("alerts") or []))
                       if d["kind"] == "switch" else
                       "CPU %.0f%% · 内存 %.0f%% · 磁盘 %.0f%% · 未运行服务 %s · 告警 %d"
                       % (d.get("cpu") or 0, d.get("mem") or 0, d.get("disk") or 0,
                          d.get("failed") or 0, len(d.get("alerts") or [])))
            store.collect_log(run_id, ip, d["name"], True, "", 260, commands,
                              summary, echo)
            ok += 1
        else:
            store.collect_log(run_id, ip, d["name"], False,
                              "连接超时：Unable to connect to host", 0, "", "")
            failed += 1

    if not clear:
        store.collect_run_finish(run_id, added, ok, failed, 0, 1800,
                                 "演示数据：成功 %d / 失败 %d / 共 %d 台" % (ok, failed, added))
    service.cache_clear()
    return {"devices": added, "ok": ok, "failed": failed, "run_id": run_id}


def service_next_id() -> int:
    from app.store import next_row_id
    return next_row_id()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="只删除这些演示设备及其数据")
    args = parser.parse_args()
    result = seed(clear=args.clear)
    if args.clear:
        print("已删除 %d 台演示设备及其巡检/告警/备份/日志" % len(DEMO))
    else:
        print("已写入 %d 台演示设备：采集成功 %d / 失败 %d（run #%d）"
              % (result["devices"], result["ok"], result["failed"], result["run_id"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
