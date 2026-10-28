# -*- coding: utf-8 -*-
"""服务器采集解析器自测：用样例回显跑一遍 Linux / Windows 解析，不连任何设备。

用法：python backend/tools/collect_server_selftest.py
"""
from __future__ import annotations

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.collect import server   # noqa: E402

LINUX = {
    "os": {
        "uname": "Linux 5.15.0-91-generic x86_64",
        "os_release": 'NAME="Ubuntu"\nVERSION="22.04.3 LTS (Jammy Jellyfish)"\n'
                      'PRETTY_NAME="Ubuntu 22.04.3 LTS"\nID=ubuntu\nVERSION_ID="22.04"',
        "hostname": "srv-app-01",
        "dmi": "Dell Inc.\nPowerEdge R750\nABC1234",
        "uptime": " 09:15:03 up 12 days,  3:21,  1 user,  load average: 0.52, 0.61, 0.58",
    },
    "cpu": {"top": "top - 09:15:03 up 12 days,  3:21,  1 user,  load average: 0.52\n"
                   "Tasks: 231 total,   1 running, 230 sleeping\n"
                   "%Cpu(s):  3.2 us,  1.0 sy,  0.0 ni, 95.4 id,  0.4 wa,  0.0 hi,  0.0 si"},
    "memory": {"free": "               total        used        free      shared  buff/cache   available\n"
                       "Mem:           64257       12345       10000         123       41912       51234\n"
                       "Swap:           8191           0        8191"},
    "disk": {"df": "Filesystem     Type  Size  Used Avail Use% Mounted on\n"
                   "/dev/sda2      ext4  200G  120G   70G  63% /\n"
                   "/dev/sdb1      xfs   2.0T  1.2T  700G  63% /data"},
    "net": {"ip": "lo               UNKNOWN        127.0.0.1/8\n"
                  "ens192           UP             10.20.30.11/24"},
    "service": {"systemctl": "  UNIT  LOAD  ACTIVE SUB  DESCRIPTION\n"
                             "0 loaded units listed."},
    "log": {"journalctl": "-- Logs begin at Mon 2026-09-01 00:00:00 CST, end at Fri 2026-10-16 --\n"
                         "Oct 16 09:15:03 srv-app-01 systemd[1]: Failed to start nginx.service.\n"
                         "Oct 16 09:16:11 srv-app-01 kernel: EXT4-fs error on sda2"},
    "temp": {"thermal": "/sys/class/thermal/thermal_zone0/temp 38500"},
    "backup": {"backup": "-rw-r--r-- 1 root root 1288490188 Oct 16 02:00 backup_20261016.tar.gz\n"
                         "-rw-r--r-- 1 root root  644245094 Oct 15 02:00 backup_20261015.tar.gz"},
}

WINDOWS = {
    "os": {
        "win-os": "Caption Microsoft Windows Server 2019 Datacenter\n"
                  "Version 10.0.17763\nBuildNumber 17763\n"
                  "Manufacturer Dell Inc.\nModel PowerEdge R750",
        "hostname": "SRV-DB-01",
        "win-uptime": "12.03:21:05.1234567",
    },
    "cpu": {"win-cpu": "Name Intel(R) Xeon(R) Gold 6338 CPU @ 2.00GHz\n"
                       "LoadPercentage 82\nNumberOfLogicalProcessors 16"},
    "memory": {"win-memory": "TotalVisibleMemorySize 65345876\nFreePhysicalMemory 7841505"},
    "disk": {"win-disk": "C: 499000000000 79840000000\nD: 2000000000000 400000000000"},
    "net": {"win-net": "Ethernet0 10.20.30.12/24"},
    "service": {"win-service": "Spooler Stopped"},
    "log": {"win-log": "2026-10-16 09:15:03 41 Error\n2026-10-16 09:16:11 1001 Error"},
    "backup": {"win-backup": "backup_20261016.zip 1200000 2026-10-16 02:00:00"},
}

FAILS = []


def check(label, ok, detail=""):
    print("%s %s%s" % ("OK  " if ok else "FAIL", label, ("" if ok else "  ← %s" % (detail,))))
    if not ok:
        FAILS.append(label)


def main() -> int:
    linux = server.build_records(LINUX, "linux", {"ip": "10.20.30.11"}, ["uname -srm"])
    check("Linux 主机名", linux["device"]["name"] == "srv-app-01", linux["device"]["name"])
    check("Linux 型号/序列号", linux["device"]["model"] == "PowerEdge R750"
          and linux["device"]["serial"] == "ABC1234", linux["device"])
    check("Linux CPU ≈ 4.6%", linux["inspection"]["device_cpu"] == 4.6,
          linux["inspection"]["device_cpu"])
    check("Linux 内存 ≈ 19.2%", linux["inspection"]["device_memory"] == 19.2,
          linux["inspection"]["device_memory"])
    disk = next((m["value"] for m in linux["metrics"] if m["metric"] == "disk"), None)
    check("Linux 磁盘 63%", disk == 63.0, disk)
    temp = next((m["value"] for m in linux["metrics"] if m["metric"] == "temp"), None)
    check("Linux 温度 38.5℃", temp == 38.5, temp)
    check("Linux 运行时长 12 天", linux["uptime_seconds"] == 12 * 86400 + 3 * 3600 + 21 * 60,
          (linux["uptime"], linux["uptime_seconds"]))
    check("Linux 无告警（资源正常）", not linux["alerts"],
          [a["content"] for a in linux["alerts"]])

    win = server.build_records(WINDOWS, "windows", {"ip": "10.20.30.12"}, ["hostname"])
    check("Windows 主机名", win["device"]["name"] == "SRV-DB-01", win["device"]["name"])
    check("Windows 系统版本", "Windows Server 2019" in win["device"]["version"],
          win["device"]["version"])
    check("Windows CPU 82%", win["inspection"]["device_cpu"] == 82.0,
          win["inspection"]["device_cpu"])
    win_mem = win["inspection"]["device_memory"]
    check("Windows 内存 ≈ 88%", win_mem is not None and 87.9 <= win_mem <= 88.1, win_mem)
    win_disk = next((m["value"] for m in win["metrics"] if m["metric"] == "disk"), None)
    check("Windows 磁盘最高 84%", win_disk == 84.0, win_disk)
    labels = [a["content"] for a in win["alerts"]]
    check("Windows 告警含 CPU/内存偏高", any("CPU" in x for x in labels)
          and any("内存" in x for x in labels), labels)
    check("Windows 告警含服务未运行", any("服务" in x for x in labels), labels)

    echo = server.build_echo(server.LINUX_BUCKETS, {
        (key, step[2]): LINUX[key][step[2]] for key in LINUX for step in []}, "linux")
    excerpt = server.raw_excerpt({
        "os": "$ uname -srm\nLinux 5.15.0-91-generic x86_64",
        "cpu": "$ top -bn1\n%Cpu(s): 3.2 us, 95.4 id",
    })
    check("回显摘要分段格式", "──── os ────" in excerpt and "──── cpu ────" in excerpt,
          excerpt[:120])

    print("")
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过：服务器采集解析器（Linux / Windows）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
