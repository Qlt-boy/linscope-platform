# -*- coding: utf-8 -*-
"""端到端自测：按前端页面的调用方式打一遍后端接口，顺带校验关键字段。

用法：python tools/smoke_check.py [--base https://127.0.0.1:1314/api]
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

FAILS: list[str] = []
TOKEN = {"value": ""}


def _login(base, username="admin", password=""):
    """全站接口已鉴权：脚本先用账号登录，拿到令牌再打其余接口。"""
    password = password or os.environ.get("NIP_ADMIN_PASSWORD", "") or "LinScope@2026"
    status, payload, _ = call(base, "/auth/login", "POST",
                              {"username": username, "password": password})
    if status == 200 and isinstance(payload, dict) and payload.get("token"):
        TOKEN["value"] = payload["token"]
        print("OK   登录 %s（令牌 %s…）" % (username, payload["token"][:8]))
        return True
    print("FAIL 登录失败：%s %s" % (status, payload))
    FAILS.append("登录失败")
    return False



def call(base, path, method="GET", body=None):
    url = base + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if TOKEN["value"] and not path.startswith("/auth/"):
        req.add_header("Authorization", "Bearer " + TOKEN["value"])
    try:
        with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            payload = json.loads(raw.decode("utf-8")) if "json" in ctype else raw
            return resp.status, payload, ctype
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300], ""


def check(name, cond, detail=""):
    flag = "OK  " if cond else "FAIL"
    if not cond:
        FAILS.append("%s %s" % (name, detail))
    print("%s %s%s" % (flag, name, ("  ← " + str(detail)) if (detail and not cond) else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://127.0.0.1:1314/api")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    if not _login(base, args.user, args.password):
        print("\n失败 1 项：登录失败（口令可用 --password 或环境变量 NIP_ADMIN_PASSWORD 指定）")
        return 1

    st, status, _ = call(base, "/system/status")
    check("系统状态 200", st == 200, st)
    check("数据源为本平台自带采集", status.get("source") == "local", status.get("source"))
    counts = status.get("counts") or {}
    devices_total = status.get("devices_total") or counts.get("devices") or 0
    print("     数据源=%s 本地设备=%s 巡检记录=%s"
          % (status.get("source"), devices_total, counts.get("inspections")))

    st, meta, _ = call(base, "/system/meta")
    check("元数据含站点名与区间", st == 200 and meta.get("periods"), meta)
    st, ov, _ = call(base, "/dashboard/overview?days=7")
    check("总览 KPI 4 张", st == 200 and len(ov.get("kpis", [])) == 4, st)
    check("健康度趋势有 7 个点", len(ov.get("trend", {}).get("labels", [])) == 7)
    trend_series = ov.get("trend", {}).get("series", [])
    check("健康度趋势有曲线且都有值",
          bool(trend_series) and all(any(v is not None for v in s["values"]) for s in trend_series),
          [s.get("name") for s in trend_series])
    res = ov.get("resources") or {}
    check("CPU/内存曲线两条", len(res.get("series", [])) == 2,
          [s.get("name") for s in res.get("series", [])])
    check("CPU 曲线有数值", any(v is not None for v in (res.get("series") or [{}])[0].get("values", [])),
          (res.get("series") or [{}])[0].get("values"))
    check("逐设备资源行有数据", len(res.get("devices", [])) > 0, len(res.get("devices", [])))
    check("整体健康度有分值", (ov.get("health") or {}).get("avg_score") is not None,
          ov.get("health"))
    check("最近巡检记录非空", len(ov.get("recent_inspections", [])) > 0)
    check("告警分级计数存在", "by_severity" in (ov.get("alerts") or {}))

    st, dev, _ = call(base, "/devices?page_size=5")
    check("设备列表分页", st == 200 and len(dev.get("rows", [])) == 5, len(dev.get("rows", [])))
    check("设备总数 > 0", (dev.get("total") or 0) > 0, dev.get("total"))
    row = (dev.get("rows") or [{}])[0]
    check("设备行含健康度与台账字段",
          "health_score" in row and "ledger" in row and "type_label" in row, list(row)[:8])
    st, filtered, _ = call(base, "/devices?keyword=%s&page_size=3" % (row.get("ip") or "10"))
    check("关键字过滤命中", (filtered.get("total") or 0) >= 1, filtered.get("total"))
    st, typ, _ = call(base, "/devices?type=server&page_size=3")
    check("按设备类型过滤", st == 200 and all(r["group_kind"] == "server" for r in typ["rows"]),
          [r["group_kind"] for r in typ.get("rows", [])])

    target = row.get("id")
    st, detail, _ = call(base, "/devices/%s" % target)
    check("设备详情", st == 200 and detail.get("device"), st)
    st, saved, _ = call(base, "/devices/%s/ledger" % target, "PUT",
                        {"owner": "张工", "asset_no": "IT-0001", "usage": "核心交换",
                         "warranty_until": "2027-12-31", "note": "联调自测写入"})
    check("台账补充可写", st == 200 and saved.get("ledger", {}).get("owner") == "张工", saved)
    st, detail2, _ = call(base, "/devices/%s" % target)
    check("台账补充已生效", (detail2.get("device", {}).get("ledger") or {}).get("asset_no") == "IT-0001")

    st, srv, _ = call(base, "/health/server")
    check("服务器健康页数据", st == 200 and srv.get("basic") and srv.get("checks"), srv.get("device"))
    st, sw, _ = call(base, "/health/switch")
    check("交换机健康页数据", st == 200 and sw.get("device"), sw.get("device"))
    check("交换机检查项 >= 10", len(sw.get("checks", [])) >= 10, len(sw.get("checks", [])))

    st, alerts, _ = call(base, "/alerts?hours=720")
    check("告警接口", st == 200 and "cards" in alerts, st)
    st, insp, _ = call(base, "/inspections?kind=switch&limit=50")
    check("巡检记录接口", st == 200 and insp.get("rows"), insp.get("total"))
    st, bk, _ = call(base, "/backups")
    check("备份接口", st == 200 and "coverage" in bk, list(bk)[:6])
    st, ar, _ = call(base, "/reports/archive")
    check("归档与模板接口", st == 200 and ar.get("templates") and ar.get("formats"), list(ar)[:6])

    for kind, fmt in (("overview", "xlsx"), ("devices", "xlsx"), ("inspection", "xlsx"),
                      ("server", "xlsx"), ("switch", "xlsx"), ("alerts", "xlsx"),
                      ("backup", "csv"),
                      # 版式报告：Word / PDF（封面 + 回显截图 + 数据分析 + 维护建议）
                      ("server", "docx"), ("server", "pdf"),
                      ("switch", "docx"), ("switch", "pdf")):
        st, payload, ctype = call(base, "/reports/export?kind=%s&format=%s" % (kind, fmt))
        size = len(payload) if isinstance(payload, bytes) else 0
        ok = st == 200 and size > 400      # 阈值放宽：数据量随台账条数变化（空库也能导出）
        check("导出 %s.%s（%d 字节）" % (kind, fmt, size), ok, (st, ctype))

    st, ar2, _ = call(base, "/reports/archive")
    check("导出后归档记录增加", (ar2.get("count") or 0) > 0, ar2.get("count"))

    print("")
    if FAILS:
        print("失败 %d 项：" % len(FAILS))
        for item in FAILS:
            print("   -", item)
        return 1
    print("全部通过：页面 → FastAPI → 本地采集库 链路数据齐备")
    return 0


if __name__ == "__main__":
    sys.exit(main())