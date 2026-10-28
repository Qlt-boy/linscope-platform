# -*- coding: utf-8 -*-
"""服务器采集端到端自测：假 SSH 服务器 → 采集 → 写库 → 报告回显截图。

用法：python backend/tools/server_collect_selftest.py
（会在临时目录建一个独立库，不碰现场数据；报告写到临时目录）
"""
from __future__ import annotations

import os
import sys
import tempfile

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(BACKEND_DIR, "tools")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, TOOLS_DIR)

TMP = tempfile.mkdtemp(prefix="server-collect-")
os.environ["NIP_DATA_DIR"] = TMP
os.environ["DATA_SOURCE"] = "local"

import fake_server_host                      # noqa: E402
from app import docreport, service           # noqa: E402
from app.collect import runner, server       # noqa: E402
from app.remote import credential_save       # noqa: E402
from app.store import get_store              # noqa: E402

FAILS = []


def check(label, ok, detail=""):
    print("%s %s%s" % ("OK  " if ok else "FAIL", label, "" if ok else "  ← %s" % (detail,)))
    if not ok:
        FAILS.append(label)


def main() -> int:
    _thread, sock, port = fake_server_host.serve(0)
    ip = "127.0.0.1"
    store = get_store()
    store.save_settings({"data_source": "local", "org_name": "林鉴知微技术服务股份有限公司"})
    store.device_upsert({"ip": ip, "name": "LAB-SRV-01", "vendor": "dell",
                         "vendor_display": "戴尔", "model": "", "kind": "server",
                         "online": True, "port": port, "source": "local"})
    credential_save(ip, {"username": "root", "password": "root123", "port": port})

    check("服务器被识别为可采集", runner.is_supported(store.devices()[0]),
          store.devices()[0])
    check("采集器选择 server", runner.profile_of(store.devices()[0]) == "server",
          runner.profile_of(store.devices()[0]))

    result = runner.run(ips=[ip], trigger="manual")
    check("采集任务成功", result.get("ok") == 1, result)

    logs = store.collect_logs(ip=ip, limit=5, with_raw=True)
    ok_logs = [row for row in logs if row.get("ok")]
    check("采集日志已留档", bool(ok_logs), logs[:1])
    excerpt = ok_logs[0].get("raw_excerpt") if ok_logs else ""
    for key in ("os", "cpu", "memory", "disk", "net", "service", "log", "temp", "backup"):
        check("回显分段 %s" % key, ("──── %s ────" % key) in (excerpt or ""),
              (excerpt or "")[:150])
    check("回显带终端提示符", "$ uname -srm" in (excerpt or ""),
          (excerpt or "")[:150])

    service.cache_clear()
    devices, _source, _info = service.devices_view()
    dev = next((d for d in devices if d["ip"] == ip), None)
    check("台账保留人工命名", bool(dev and dev["name"] == "LAB-SRV-01"), dev and dev["name"])
    check("台账回填型号", bool(dev and dev["model"] == "PowerEdge R750"), dev and dev["model"])
    check("归到服务器分组", bool(dev and dev["group_kind"] == "server"),
          dev and dev["group_kind"])
    check("CPU 写进巡检记录", bool(dev and dev["cpu"] is not None), dev and dev["cpu"])
    check("内存写进巡检记录", bool(dev and dev["memory"] is not None), dev and dev["memory"])
    page = service.health_page("server", dev["id"]) if dev else {}
    disk = page.get("resources") or []
    check("健康页可用", bool(page.get("device")), page.get("device"))
    check("磁盘写进指标", any("磁盘" in (x.get("name") or "")
                            and x.get("value") not in ("未采集", None) for x in disk), disk)
    env = page.get("environment") or []
    check("温度写进指标", any("温度" in (x.get("name") or "")
                            and x.get("value") not in ("未采集", None) for x in env), env)

    checks = {c.get("item"): c.get("result") for c in page.get("checks") or []}
    check("健康页检查项有结果", all(v for v in checks.values()) and bool(checks), checks)

    filename, payload, stats = docreport.build("server", {"hours": 24 * 7}, "docx")
    check("服务器报告可生成", len(payload) > 100000, (filename, len(payload), stats))
    check("报告含回显截图", (stats.get("images") or 0) >= 5, stats)

    parsed = server.parse_echo if hasattr(server, "parse_echo") else None
    sock.close()
    print("")
    print("临时库：%s" % TMP)
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过：服务器采集 → 回显留档 → 报告截图")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
