# -*- coding: utf-8 -*-
"""把「几条华为测试数据」灌进平台：清掉旧的样例数据 → 建 5 台华为交换机 → 配凭据 → 采一轮。

用途：验收/演示「自带采集（华为 VRP）」这条链路，不需要真设备 —— 配合
`backend/tools/fake_huawei_switch.py --count 5`（本机假华为靶机，127.0.0.2:2223-2227）。

做三件事，全部走平台自己的 HTTP 接口（跟你在页面上点是一样的）：
 1. 备份并清空本地库里的旧样例数据（设备/巡检/监控/指标/告警/备份）；
 2. 新增 5 台华为测试设备 + 凭据（netadmin / netadmin123）；
 3. 跑一轮采集，打印每台结果。

用法：
    python backend/tools/seed_huawei_lab.py --password <平台admin口令> [--keep-old]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import ssl
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
DB = os.path.join(BACKEND, "data", "netinspect.sqlite3")
BASE = os.environ.get("NIP_BASE", "https://127.0.0.1:1314")

DEVICES = [
    ("127.0.0.2", "HW-CORE-SW01", "S6720-30C-EI-24S", "核心网", "机房A", 2223, "gateway", "core_switch"),
    ("127.0.0.3", "HW-AGG-SW01", "S5731-H48T4XC", "汇聚接入", "机房A", 2223, "", "aggregation_switch"),
    ("127.0.0.4", "HW-ACC-SW01", "S5720-28X-SI-AC", "汇聚接入", "机房A", 2223, "access", "access_switch"),
    ("127.0.0.5", "HW-ACC-SW02", "S5735-L24T4S-A", "汇聚接入", "机房B", 2223, "access", "access_switch"),
    ("127.0.0.6", "HW-EDGE-SW01", "S5720-52X-SI-AC", "汇聚接入", "机房B", 2223, "", "access_switch"),
    # 一条"采不到"的测试数据：地址上没人监听，用来看失败日志长什么样
    ("127.0.0.9", "HW-OFFLINE-01", "S5720-28X-SI-AC", "实验区", "本机", 2223, "", "access_switch"),
]
TOKEN = {"value": ""}
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def call(path, method="GET", body=None):
    url = BASE + "/api" + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if TOKEN["value"]:
        req.add_header("Authorization", "Bearer " + TOKEN["value"])
    try:
        with urllib.request.urlopen(req, timeout=180, context=SSL_CONTEXT) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw.strip().startswith(("{", "[")) else raw)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def login(password: str, user: str = "admin") -> None:
    status, payload = call("/auth/login", "POST",
                           {"username": user, "password": password})
    if status != 200 or not isinstance(payload, dict) or not payload.get("token"):
        raise SystemExit("登录失败：%s %s" % (status, payload))
    TOKEN["value"] = payload["token"]
    print("OK   登录 %s" % user)


def purge(keep_old: bool) -> None:
    if keep_old:
        print("跳过清库（--keep-old）")
        return
    if not os.path.exists(DB):
        print("没有本地库，跳过清库")
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = DB + ".backup-" + stamp
    shutil.copy2(DB, backup)
    print("OK   已备份本地库 → %s" % backup)
    con = sqlite3.connect(DB)
    for table in ("devices", "inspections", "monitors", "metrics", "alerts",
                  "backups", "ledger", "collect_logs", "collect_runs", "exports",
                  "auth_sessions", "audit"):
        try:
            con.execute("DELETE FROM %s" % table)
        except sqlite3.Error:
            pass
    con.commit()
    con.close()
    print("OK   已清空旧样例数据（要恢复：把上面的备份文件改回 netinspect.sqlite3 并重启后端）")


def add_devices() -> None:
    for ip, name, model, group, region, port, role, kind in DEVICES:
        status, payload = call("/devices", "POST", {
            "ip": ip, "name": name, "model": model, "group": group,
            "region": region, "port": port, "role": role, "kind": kind,
            "vendor": "huawei"})
        if status != 200:
            status, payload = call("/devices/" + ip, "PUT", {
                "name": name, "model": model, "group": group, "region": region,
                "port": port, "role": role, "kind": kind})
        print("  %-14s %-16s port=%-5s %s" % (ip, name, port,
                                              "OK" if status == 200 else "失败：%s" % payload))
        call("/remote/credentials/" + ip, "PUT", {
            "username": "netadmin", "password": "netadmin123", "port": port,
            "auth": "password", "note": "华为测试设备（自带采集）"})
    print("OK   5 台测试设备 + 1 台不可达设备已就绪（凭据 netadmin/netadmin123）")


def collect() -> None:
    status, payload = call("/collect/run", "POST", {"with_config": True})
    if status != 200:
        raise SystemExit("采集失败：%s %s" % (status, payload))
    print("OK   %s（%s ms）" % (payload.get("message"), payload.get("duration_ms")))
    for item in payload.get("details", []):
        print("  %-13s %s" % (item["ip"], item.get("summary") or ("失败：" + item.get("error", ""))))


def main() -> None:
    global BASE
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default=os.environ.get("NIP_ADMIN_PASSWORD", ""))
    parser.add_argument("--keep-old", action="store_true", help="保留库里已有数据")
    args = parser.parse_args()
    BASE = args.base.rstrip("/")
    if not args.password:
        raise SystemExit("请用 --password 或环境变量 NIP_ADMIN_PASSWORD 提供平台 admin 口令")

    purge(args.keep_old)          # 先清库：清 auth_sessions 会把当前令牌一起废掉
    login(args.password, args.user)
    add_devices()
    time.sleep(0.5)
    collect()
    status, overview = call("/collect/overview")
    print("完成：设备 %s 台，凭据就绪 %s 台"
          % (overview.get("devices_total"), overview.get("credential_ready")))


if __name__ == "__main__":
    main()