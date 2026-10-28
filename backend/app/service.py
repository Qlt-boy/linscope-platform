# -*- coding: utf-8 -*-
"""业务取数：页面要什么，这里组装什么。

**纯本地**：所有数据都来自本平台自己的 SQLite 库 ——
自带采集（SSH 只读）把设备台账、巡检、监控、指标、告警、配置备份写进来，
页面、Excel / CSV 报表与 Word / PDF 版式报告都只读这张库。

不依赖任何外部巡检平台，也没有「数据源切换」：一台设备配好 SSH 凭据后，
由采集任务（定时 / 手动）拉取数据，取不到的字段如实显示「未采集」。
"""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timedelta

from . import normalize as nz
from .store import get_store

_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, object]] = {}


# ------------------------------------------------------------------ 基础设施
def settings() -> dict:
    return get_store().get_settings()


def cache_get(key: str):
    ttl = float(settings().get("cache_ttl") or 20)
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and (time.time() - hit[0]) < ttl:
            return hit[1]
    return None


def cache_put(key: str, value) -> None:
    with _LOCK:
        _CACHE[key] = (time.time(), value)


def cache_clear() -> None:
    with _LOCK:
        _CACHE.clear()


def status() -> dict:
    """本地数据体检：库里有多少料、凭据配了几台、最近一次采集是什么时候。"""
    values = settings()
    store = get_store()
    counts = store.counts()
    stats7 = store.collect_stats(7)
    runs = store.collect_runs(limit=1)
    last = runs[0] if runs else {}
    credentials = 0
    try:
        from . import remote as remote_login
        credentials = len(remote_login.credentials_list())
    except Exception:                                       # noqa: BLE001
        pass
    return {
        "settings": {
            "site_name": values.get("site_name"),
            "org_name": values.get("org_name"),
            "period_days": values.get("period_days"),
        },
        "counts": counts,
        "devices_total": counts.get("devices") or 0,
        "credentials_ready": credentials,
        "collect": {
            "runs_7d": stats7.get("runs"),
            "success_rate": stats7.get("success_rate"),
            "last_run": last or None,
            "last_collect_at": (last.get("finished_at") or last.get("started_at") or ""),
        },
        "source": "local",
        "source_label": "本平台自带采集",
    }


#: 采集来源标签（纯本地模式只有一种来源）
COLLECT_CMD_LABEL = "本平台采集"


def source_label(source: str = "local") -> str:
    return "本平台自带采集"


# ------------------------------------------------------------------ 取数（只读本地库）
def fetch(kind: str, hours: int = -1, use_cache: bool = True):
    """取一类本地数据，返回 (rows, "local", info)。

    数据由自带采集写入（collect_runs / collect_logs 留痕），这里只读。
    """
    key = "rows:%s:%s" % (kind, hours)
    if use_cache:
        cached = cache_get(key)
        if cached:
            return cached
    result = (_local_rows(kind, hours), "local", {"error": ""})
    cache_put(key, result)
    return result


def _local_rows(kind: str, hours: int):
    store = get_store()
    hours = hours if hours and hours > 0 else None
    if kind == "devices":
        return store.devices()
    if kind == "inspections":
        return store.inspections(hours=hours)
    if kind == "monitors":
        return store.monitors(hours=hours)
    if kind == "metrics":
        return store.metrics(hours=hours)
    if kind == "alerts":
        return store.alerts(hours=hours)
    if kind == "backups":
        return store.backup_rows()
    return []


# 兼容旧调用名（报表/工具里可能还在用）
_mirror_rows = _local_rows


# ------------------------------------------------------------------ 组合视图
def sort_desc(rows: list, field: str) -> list:
    """按时间字段倒序（采集写入是按 id 递增，不能直接当「最新」用）。"""
    return sorted(rows, key=lambda r: str(r.get(field) or ""), reverse=True)


def _index_by_device(rows: list) -> dict:
    out: dict = {}
    for row in rows:
        key = row.get("device_id")
        if key is None:
            continue
        out.setdefault(key, []).append(row)
    return out


def _latest_by_device(rows: list) -> dict:
    out: dict = {}
    for row in rows:
        key = row.get("device_id")
        if key is None or key in out:
            continue
        out[key] = row
    return out


def devices_view(hours: int = 24 * 30, pending: bool = False):
    """设备台账：默认只返回已入台账设备；pending=True 返回待采集设备。"""
    devices, source, info = fetch("devices")
    devices = [d for d in devices if bool(d.get("pending_collection")) == bool(pending)]
    inspections, _, _ = fetch("inspections", hours=hours)
    monitors, _, _ = fetch("monitors", hours=hours)
    ledger = get_store().ledger_all()
    # 注意：设备 id 有两个来源（历史导入的数据 / 本平台本地台账），两边的 id 不是
    # 同一套命名空间，**必须按 IP 关联**，否则会出现"张冠李戴"（把别人的 CPU 显示到这台）。
    latest_insp = {}
    for rec in sorted(inspections, key=lambda r: str(r.get("inspected_at") or ""),
                      reverse=True):
        key = rec.get("device_ip") or rec.get("device_id")
        latest_insp.setdefault(key, rec)
    latest_mon = {}
    for rec in sorted(monitors, key=lambda r: str(r.get("collected_at") or ""),
                      reverse=True):
        key = rec.get("device_ip") or rec.get("device_id")
        latest_mon.setdefault(key, rec)
    rows = [nz.device_view(dev, latest_insp.get(dev.get("ip")) or latest_insp.get(dev.get("id")),
                           latest_mon.get(dev.get("ip")) or latest_mon.get(dev.get("id")),
                           ledger.get(dev.get("ip")))
            for dev in devices]
    # 本平台自己新增/采集回来的设备（本地台账）也一并列出：即使台账里
    # 没有这台设备，页面上也能看到、能配凭据、能采集。
    seen = {row["ip"] for row in rows}
    try:
        for local in get_store().devices(include_pending=True):
            if not local.get("ip") or local["ip"] in seen:
                continue
            if bool(local.get("pending_collection")) != bool(pending):
                continue
            rows.append(nz.device_view(local,
                                       latest_insp.get(local.get("ip")) or latest_insp.get(local.get("id")),
                                       latest_mon.get(local.get("ip")) or latest_mon.get(local.get("id")),
                                       ledger.get(local["ip"])))
    except Exception:
        pass
    return rows, source, info


def overview(period_days: int = 7) -> dict:
    """巡检总览：KPI + 健康度趋势 + CPU/内存曲线 + 最近巡检 + 告警卡片。"""
    hours = max(1, period_days) * 24
    devices, source, info = devices_view(hours=max(hours, 24 * 7))
    inspections, _, _ = fetch("inspections", hours=max(hours, 24 * 7))
    monitors, _, _ = fetch("monitors", hours=max(hours, 24 * 7))
    metrics, _, _ = fetch("metrics", hours=max(hours, 24 * 7))
    alerts, _, _ = fetch("alerts", hours=max(hours, 24 * 7))
    store = get_store()

    scored = [d for d in devices if d["health_score"] is not None]
    avg_score = round(sum(d["health_score"] for d in scored) / len(scored), 1) \
        if scored else None

    kind_counts = {"server": 0, "switch": 0, "security": 0, "other": 0}
    for dev in devices:
        kind_counts[dev["group_kind"]] = kind_counts.get(dev["group_kind"], 0) + 1
    online = len([d for d in devices if d["online"]])

    # 异常检查项：巡检判定异常 + 内存/CPU 偏高 + 离线 + 告警未恢复
    abnormal = []
    for dev in devices:
        for reason in dev["health_reasons"]:
            abnormal.append({"device": dev["name"], "ip": dev["ip"], "reason": reason})
    open_alerts = [a for a in alerts if (a.get("status") or "") not in ("resolved", "closed")]
    alert_groups = aggregate_alerts(alerts)
    alert_sorted = sorted(alerts, key=lambda r: str(r.get("triggered_at") or ""), reverse=True)
    changed = [a for a in alert_sorted if nz.is_change_metric(a.get("metric"))]

    # 健康度趋势：按天聚合巡检分数的均值
    trend = _trend_series(inspections, devices, hours)
    cpu_series, mem_series = _resource_series(monitors, hours)
    device_resources = _device_resource_rows(devices, monitors)

    kpis = [
        {"label": "受检设备总数", "value": str(len(devices)), "unit": "台设备",
         "note": "服务器 %d · 网络设备 %d · 安全设备 %d · 在线 %d"
                 % (kind_counts.get("server", 0),
                    kind_counts.get("switch", 0),
                    kind_counts.get("security", 0), online),
         "tone": "success" if devices else "muted"},
        {"label": "平均健康度", "value": ("%.1f" % avg_score) if avg_score is not None else "—",
         "unit": "/ 100 分",
         "note": ("共 %d 台有巡检结论" % len(scored)) if scored else "尚无巡检数据",
         "tone": "success" if (avg_score or 0) >= 95 else "warning"},
        {"label": "异常检查项", "value": str(len(abnormal)), "unit": "项异常",
         "note": "全部检查项通过 · 无告警信息" if not abnormal
                 else "涉及 %d 台设备" % len({a["device"] for a in abnormal}),
         "tone": "success" if not abnormal else "warning"},
        {"label": "巡检报告", "value": str(store.counts()["exports"]), "unit": "份已归档",
         "note": "本平台导出记录 · 可在报告中心下载",
         "tone": "muted"},
    ]

    recent = []
    for dev in sorted(devices, key=lambda d: d["last_inspected_at"] or "", reverse=True):
        if not dev["last_inspected_at"]:
            continue
        recent.append({
            "target": dev["name"], "type": dev["type_label"],
            "time": dev["last_inspected_text"], "owner": dev["ledger"].get("owner") or "—",
            "asset_no": dev["ledger"].get("asset_no") or "—",
            "location": dev["ledger"].get("location") or "—",
            "score": ("%.1f" % dev["health_score"]) if dev["health_score"] is not None else "—",
            "status": dev["health_label"], "tone": dev["health_tone"],
        })
    if not recent:
        recent = [{
            "target": d["name"], "type": d["type_label"], "time": "尚未巡检",
            "owner": d["ledger"].get("owner") or "—",
            "asset_no": d["ledger"].get("asset_no") or "—",
            "location": d["ledger"].get("location") or "—",
            "score": "—",
            "status": d["health_label"], "tone": d["health_tone"],
        } for d in devices[:8]]

    type_rate = []
    for group, label in (("server", "服务器设备"), ("switch", "网络设备"), ("security", "安全设备")):
        group_rows = [d for d in devices if d["group_kind"] == group and d["health_score"] is not None]
        if group_rows:
            value = "%.1f%%" % (sum(d["health_score"] for d in group_rows) / len(group_rows))
        else:
            group_rows_all = [d for d in devices if d["group_kind"] == group]
            value = "—" if group_rows_all else "无设备"
        type_rate.append({"name": label, "value": value})
    online_rate = ("%.1f%%" % (100.0 * online / len(devices))) if devices else "—"
    type_rate.append({"name": "设备在线率", "value": online_rate})

    severity = {"critical": 0, "major": 0, "warning": 0, "info": 0}
    for item in alerts:
        key = nz.severity_view(item.get("severity"))[0]
        severity[key] = severity.get(key, 0) + 1

    return {
        "source": source, "source_info": info,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "period": {"days": period_days, "label": _period_label(hours)},
        "kpis": kpis,
        "counts": {"devices": len(devices), "online": online,
                   "servers": kind_counts.get("server", 0),
                   "switches": kind_counts.get("switch", 0),
                   "security": kind_counts.get("security", 0),
                   "inspections": len(inspections), "alerts": len(alerts),
                   "open_alerts": len(open_alerts)},
        "health": {"avg_score": avg_score, "summary": type_rate},
        "trend": trend,
        "resources": {"labels": cpu_series["labels"], "series": [
            {"name": "CPU 平均使用率", "color": "#1A73E8", "values": cpu_series["values"]},
            {"name": "内存平均使用率", "color": "#34A853", "values": mem_series["values"]},
        ], "unit": "%", "devices": device_resources},
        "recent_inspections": recent[:8],
        "abnormal": abnormal[:20],
        "alerts": {
            "total": len(alerts), "open": len(open_alerts),
            "group_total": len(alert_groups),
            "collapsed": max(0, len(alerts) - len(alert_groups)),
            "by_severity": severity,
            # 自带采集的「变化检测」告警单独计数：跟上一轮比出来的变化（CPU 突增、
            # 端口新变 down、设备重启…），跟固定阈值告警分开显示
            "change_total": len(changed),
            "recent": [{
                "id": a.get("id"), "title": a.get("content") or a.get("rule") or "告警",
                "source": a.get("source_display") or a.get("source") or "",
                "severity": nz.severity_view(a.get("severity"))[0],
                "status": a.get("status_display") or a.get("status") or "",
                "device": a.get("device") or a.get("device_ip") or "",
                "time": nz.fmt_time(a.get("triggered_at")),
                "metric": a.get("metric") or "",
                "change": nz.is_change_metric(a.get("metric")),
                "change_label": nz.change_metric_label(a.get("metric")),
            } for a in sorted(alert_sorted, key=lambda r: str(r.get("triggered_at") or ""),
                              reverse=True)[:6]],
            "change_recent": [{
                "title": a.get("content") or a.get("rule") or "告警",
                "device": a.get("device") or a.get("device_ip") or "",
                "time": nz.fmt_time(a.get("triggered_at")),
                "change_label": nz.change_metric_label(a.get("metric")),
                "severity": nz.severity_view(a.get("severity"))[0],
            } for a in changed[:8]],
        },
    }


def wall_view() -> dict:
    """大屏轮播数据：每台设备的核心采集指标，交换机 / 服务器分两块。

    只取大屏需要的字段（不做完整健康页那种多表联查），一次返回整屏数据，
    前端按设备自动轮播，不用逐台请求。
    """
    devices, source, _info = devices_view()
    store = get_store()
    inspections = store.inspections()
    latest: dict = {}
    for rec in sorted(inspections, key=lambda r: str(r.get("inspected_at") or "")):
        latest[rec.get("device_ip") or rec.get("device_id")] = rec
    metrics = store.metrics()
    monitors = store.monitors()
    all_alerts = store.alerts()
    backups = store.backup_rows()
    insp_by_ip: dict = {}
    mon_by_ip: dict = {}
    for rec in inspections:
        insp_by_ip.setdefault(rec.get("device_ip") or "", []).append(rec)
    for rec in monitors:
        mon_by_ip.setdefault(rec.get("device_ip") or "", []).append(rec)

    def trend_of(ip: str, dev: dict) -> dict:
        points = []
        for rec in mon_by_ip.get(ip, []):
            if rec.get("cpu") is None and rec.get("memory") is None:
                continue
            hs = rec.get("health_score")
            if hs is None:
                hs = nz.health(dev, {}, rec).get("score")
            points.append((rec.get("collected_at") or "", rec.get("cpu"),
                           rec.get("memory"), hs))
        if not points:
            for rec in insp_by_ip.get(ip, []):
                if rec.get("cpu") is None and rec.get("memory") is None:
                    continue
                hs = rec.get("health_score")
                if hs is None:
                    hs = nz.health(dev, rec, {}).get("score")
                points.append((rec.get("inspected_at") or "", rec.get("cpu"),
                               rec.get("memory"), hs))
        points.sort(key=lambda x: x[0])
        # 同一采集时点只保留一条，避免重复节点叠在一起。
        dedup = {}
        for stamp, cpu, memory, health in points:
            dedup[stamp] = (stamp, cpu, memory, health)
        points = list(dedup.values())[-12:]
        return {
            "labels": [(nz.fmt_time(stamp)[-5:] if stamp else "--:--")
                       for stamp, _, _, _ in points],
            "cpu": [cpu for _, cpu, _, _ in points],
            "memory": [memory for _, _, memory, _ in points],
            "health": [health for _, _, _, health in points],
        }

    def item(dev: dict) -> dict:
        insp = latest.get(dev["ip"]) or {}
        mine = [a for a in all_alerts if a.get("device_ip") == dev["ip"]]
        mine.sort(key=lambda a: str(a.get("triggered_at") or ""), reverse=True)
        unresolved = [a for a in mine
                      if (a.get("status") or "") not in ("resolved", "closed")]
        recent = []
        for alert in unresolved[:6]:
            try:
                label = nz.severity_view(alert.get("severity"))[1]
            except Exception:                               # noqa: BLE001
                label = alert.get("severity") or ""
            recent.append({"severity": label, "content": alert.get("content") or "",
                           "time": nz.fmt_time(alert.get("triggered_at"))})
        ports = insp.get("ports") if isinstance(insp.get("ports"), list) else []
        port_list = [{"name": p.get("name") or "port",
                      "up": bool(p.get("up")) if p.get("up") is not None else None,
                      "description": p.get("description") or ""} for p in ports]
        alert_by_severity = {"critical": 0, "major": 0, "warning": 0, "info": 0}
        for alert in unresolved:
            sev = nz.severity_view(alert.get("severity"))[0]
            alert_by_severity[sev] = alert_by_severity.get(sev, 0) + 1
        now = datetime.now()
        alert_trend = {"labels": [], "values": []}
        for step in range(11, -1, -1):
            start = now - timedelta(minutes=(step + 1) * 30)
            end = now - timedelta(minutes=step * 30)
            count = 0
            for alert in mine:
                dt = nz.parse_time(alert.get("triggered_at"))
                if dt is not None and start <= dt <= end:
                    count += 1
            alert_trend["labels"].append(end.strftime("%H:%M"))
            alert_trend["values"].append(count)
        base = {
            "id": dev["id"], "name": dev["name"], "ip": dev["ip"],
            "type_label": dev["type_label"], "model": dev["model"] or "",
            "version": dev["version"] or "", "group": dev["group"] or "",
            "region": dev["region"] or "", "online": bool(dev["online"]),
            "health_score": dev["health_score"], "health_label": dev["health_label"],
            "health_tone": dev["health_tone"],
            "cpu": dev["cpu"], "memory": dev["memory"],
            "last_inspected": dev["last_inspected_text"] or "尚未巡检",
            "alerts": len(mine), "unresolved": len(unresolved),
            "recent_alerts": recent, "alert_by_severity": alert_by_severity,
            "alert_trend": alert_trend, "port_list": port_list,
            "backups": len([b for b in backups if b.get("device_ip") == dev["ip"]]),
            "issues": insp.get("issues") or "",
            "trend": trend_of(dev["ip"], dev),
        }
        if dev["group_kind"] == "server":
            base.update({
                "disk": nz.metric_value(metrics, dev["id"], ("disk", "磁盘")),
                "temp": nz.metric_value(metrics, dev["id"], ("temp", "温度")),
                "failed_services": nz.metric_value(metrics, dev["id"],
                                                   ("failed", "服务")),
            })
        else:
            # 离线设备不把上一轮的端口/STP 当成"当前状态"展示
            live = bool(dev["online"])
            base.update({
                "ports_up": len([p for p in ports if p.get("up")]) if live else None,
                "ports_down": len([p for p in ports if p.get("up") is False]) if live else None,
                "error_ports": insp.get("error_ports") if live else None,
                "error_total": insp.get("error_total") if live else None,
                "stp_state": (insp.get("stp_state") or "") if live else "",
                "stp_forward": insp.get("stp_forward") if live else None,
                "stp_blocked": insp.get("stp_blocked") if live else None,
                "lldp": len(insp.get("lldp") or []) if live else None,
            })
        return base

    switches, servers, security = [], [], []
    for dev in devices:
        row = item(dev)
        group = dev["group_kind"]
        if group == "server":
            servers.append(row)
        elif group == "security":
            security.append(row)
        else:
            switches.append(row)

    def order(rows):
        return sorted(rows, key=lambda r: (r["health_score"] is None,
                                           r["health_score"] if r["health_score"] is not None
                                           else 0, r["name"]))

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "source_label": source_label(source),
        "rotate_seconds": 8,
        "switch": order(switches),
        "server": order(servers),
        "security": order(security),
        "summary": {
            "devices": len(devices), "switch": len(switches), "server": len(servers),
            "security": len(security),
            "online": len([d for d in devices if d.get("online")]),
            "alerts": len([a for a in all_alerts
                           if (a.get("status") or "") not in ("resolved", "closed")]),
        },
    }


def _period_label(hours: int) -> str:
    end = datetime.now()
    start = end - timedelta(hours=hours)
    return "%s - %s" % (start.strftime("%Y.%m.%d"), end.strftime("%Y.%m.%d"))


def _trend_series(inspections: list, devices: list, hours: int) -> dict:
    """按天算健康度均值（服务器 / 交换机 两条线）。"""
    days = max(2, min(14, hours // 24))
    end = datetime.now().date()
    dates = [end - timedelta(days=days - 1 - i) for i in range(days)]
    kind_of = {d["ip"]: d["group_kind"] for d in devices}
    kind_of.update({d["id"]: d["group_kind"] for d in devices})
    buckets = {d: {"server": [], "switch": [], "security": []} for d in dates}
    for rec in inspections:
        dt = nz.parse_time(rec.get("inspected_at"))
        if dt is None or dt.date() not in buckets:
            continue
        group = kind_of.get(rec.get("device_ip") or rec.get("device_id"), "switch")
        score = nz.health({"online": True}, rec, {})["score"]
        if score is None:
            continue
        buckets[dt.date()][group if group in ("server", "switch", "security") else "switch"].append(score)
    labels = [d.strftime("%m.%d") for d in dates]

    def series(kind):
        values = []
        for day in dates:
            got = buckets[day][kind]
            values.append(round(sum(got) / len(got), 1) if got else None)
        return values

    all_series = [
        {"name": "服务器", "color": "#1A73E8", "values": series("server")},
        {"name": "网络设备", "color": "#34A853", "values": series("switch")},
        {"name": "安全设备", "color": "#F59E0B", "values": series("security")},
    ]
    # 整条都没数据的序列不画（例如还没有服务器巡检记录）
    drawn = [s for s in all_series if any(v is not None for v in s["values"])]
    return {"labels": labels, "series": drawn,
            "legend": ["健康度评分", "近 %d 天" % days],
            "yTicks": [100, 95, 90, 85, 80]}


def _resource_series(monitors: list, hours: int) -> tuple[dict, dict]:
    """按天算 CPU / 内存 均值（SNMP 采集 + 巡检记录里的数值）。"""
    days = max(2, min(14, hours // 24))
    end = datetime.now().date()
    dates = [end - timedelta(days=days - 1 - i) for i in range(days)]
    cpu = {d: [] for d in dates}
    mem = {d: [] for d in dates}
    for rec in monitors:
        dt = nz.parse_time(rec.get("collected_at"))
        if dt is None or dt.date() not in cpu:
            continue
        if rec.get("cpu") is not None:
            cpu[dt.date()].append(float(rec["cpu"]))
        if rec.get("memory") is not None:
            mem[dt.date()].append(float(rec["memory"]))
    labels = [d.strftime("%m.%d") for d in dates]
    return ({"labels": labels,
             "values": [round(sum(v) / len(v), 1) if v else None for v in cpu.values()]},
            {"labels": labels,
             "values": [round(sum(v) / len(v), 1) if v else None for v in mem.values()]})


def _device_resource_rows(devices: list, monitors: list) -> list:
    """每台设备当前 CPU / 内存（取最近一次采集）。"""
    latest = {}
    for rec in sorted(monitors, key=lambda r: str(r.get("collected_at") or ""),
                      reverse=True):
        latest.setdefault(rec.get("device_ip") or rec.get("device_id"), rec)
    rows = []
    for dev in devices:
        rec = latest.get(dev["ip"]) or latest.get(dev["id"]) or {}
        cpu = dev["cpu"] if dev["cpu"] is not None else _num(rec.get("cpu"))
        mem = dev["memory"] if dev["memory"] is not None else _num(rec.get("memory"))
        if cpu is None and mem is None:
            continue
        rows.append({"name": dev["name"], "ip": dev["ip"], "type": dev["type_label"],
                     "cpu": cpu, "memory": mem,
                     "time": nz.fmt_time(rec.get("collected_at"))})
    return rows


def _num(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None

# ------------------------------------------------------------------ 设备详情 / 健康检查
def _belongs_to_device(row: dict, device: dict) -> bool:
    """Do not associate a different IP merely because a historical ID collides."""
    if row.get("device_ip"):
        return str(row["device_ip"]) == str(device.get("ip") or "")
    return row.get("device_id") is not None and str(row["device_id"]) == str(device.get("id"))


def _find_device(devices: list, key) -> dict | None:
    if key in (None, ""):
        return devices[0] if devices else None
    text = str(key)
    for dev in devices:
        if text == str(dev.get("id")) or text == dev.get("ip") \
                or text.lower() == (dev.get("name") or "").lower():
            return dev
    return None


def device_detail(key) -> dict:
    devices, source, info = devices_view()
    dev = _find_device(devices, key)
    if dev is None:
        return {"device": None, "source": source, "source_info": info}
    inspections, _, _ = fetch("inspections")
    monitors, _, _ = fetch("monitors")
    alerts, _, _ = fetch("alerts", hours=24 * 90)
    own_insp = sort_desc([r for r in inspections
                          if _belongs_to_device(r, dev)],
                         "inspected_at")
    own_mon = sort_desc([r for r in monitors
                         if _belongs_to_device(r, dev)],
                        "collected_at")
    own_alerts = sort_desc([a for a in alerts
                            if _belongs_to_device(a, dev)], "triggered_at")
    lldp = _lldp_of(dev, own_insp[0] if own_insp else None)
    return {
        "device": dev,
        "source": source, "source_info": info,
        "latest_inspection": own_insp[0] if own_insp else None,
        "latest_monitor": own_mon[0] if own_mon else None,
        "inspections": own_insp[:20],
        "monitors": own_mon[:20],
        "alerts": own_alerts[:20],
        "lldp_neighbors": lldp,
        "advice": _advice(dev, own_insp[0] if own_insp else None,
                          own_alerts),
    }


def _lldp_of(dev: dict, inspection: dict | None = None) -> list:
    """设备 LLDP 邻居：读本平台自带采集在巡检快照里留下的邻居表。

    采集器执行 display lldp neighbor 后把邻居写进 inspection.payload.lldp；
    没有采到就返回空列表，页面照实显示「未采集到 LLDP 邻居」。
    """
    rows = (inspection or {}).get("lldp") or []
    by_ip = {}
    by_name = {}
    try:
        current, _, _ = devices_view()
        by_ip = {d.get("ip"): d for d in current if d.get("ip")}
        by_name = {(d.get("name") or "").strip().lower(): d for d in current if d.get("name")}
    except Exception:
        pass
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        neighbor_ip = row.get("neighbor_ip") or row.get("ip") or ""
        neighbor_name = row.get("neighbor_name") or row.get("device") or ""
        known = by_ip.get(neighbor_ip) or by_name.get(neighbor_name.strip().lower())
        out.append({
            "local_port": row.get("local_port") or row.get("local") or "",
            "neighbor_name": neighbor_name,
            "neighbor_port": row.get("neighbor_port") or row.get("port") or "",
            "neighbor_ip": neighbor_ip,
            "known_device": bool(known or row.get("known_device")),
            "known_device_ip": (known or {}).get("ip") or "",
            "known_device_name": (known or {}).get("name") or "",
        })
    return out


def _advice(dev: dict, inspection: dict | None, alerts: list) -> list:
    tips = []
    for reason in dev.get("health_reasons") or []:
        tips.append("%s：%s" % (dev["name"], reason))
    if not inspection:
        tips.append("%s 尚无巡检记录，请在「采集任务」页对该设备发起一次采集。" % dev["name"])
    if alerts:
        tips.append("%s 近期有 %d 条告警，处置后复跑一次巡检以确认恢复。"
                    % (dev["name"], len(alerts)))
    if not tips:
        tips.append("%s 各项检查通过，按现有周期保持例行巡检即可。" % dev["name"])
    tips.append("定期备份设备配置，保留可回滚的版本快照。")
    return tips


def _result_tag(ok: bool | None) -> tuple[str, str]:
    if ok is None:
        return "未采集", "neutral"
    return ("正常", "success") if ok else ("异常", "danger")


def _switch_checks(dev: dict, insp: dict | None, mon: dict | None,
                   lldp: list, alerts: list, backups: list) -> list:
    """交换机检查项：全部落在本平台采集到的真实字段上。"""
    insp = insp or {}
    mon = mon or {}
    cpu = _num(insp.get("cpu")) if insp.get("cpu") is not None else _num(mon.get("cpu"))
    mem = _num(insp.get("memory")) if insp.get("memory") is not None else _num(mon.get("memory"))
    err_total = _num(insp.get("error_total"))
    err_ports = _num(insp.get("error_ports"))
    stp_state = (insp.get("stp_state") or "").lower()
    stp_text = {"enabled": "启用", "disabled": "禁用", "unknown": "未知"}.get(stp_state, "未知")
    version = dev.get("version") or ""
    online = dev.get("online")
    checks = []

    checks.append({
        "item": "设备运行状态", "cmd": "SSH 采集登录",
        "purpose": "设备在线可管理" if online else "设备当前不可达，请检查链路与电源",
        "ok": bool(online)})
    checks.append({
        "item": "软件版本", "cmd": "display version",
        "purpose": version or "尚未采集到版本号（需 display version 回显）",
        "ok": bool(version) if version else None})
    checks.append({
        "item": "CPU 利用率", "cmd": "display cpu-usage",
        "purpose": ("当前 %.0f%%，%s" % (cpu, "低于 80% 告警阈值" if cpu < nz.CPU_WARN_PCT
                                        else "已达到告警阈值" if cpu < nz.CPU_ERR_PCT
                                        else "已超过 90% 严重阈值"))
                   if cpu is not None else "未能解析 CPU 使用率（巡检未回显）",
        "ok": None if cpu is None else cpu < nz.CPU_WARN_PCT})
    checks.append({
        "item": "内存利用率", "cmd": "display memory",
        "purpose": ("当前 %.0f%%，%s" % (mem, "低于 80% 告警阈值" if mem < nz.MEM_WARN_PCT
                                        else "已达到告警阈值" if mem < nz.MEM_ERR_PCT
                                        else "已超过 90% 严重阈值"))
                   if mem is not None else "未能解析内存使用率（巡检未回显）",
        "ok": None if mem is None else mem < nz.MEM_WARN_PCT})
    checks.append({
        "item": "接口错包统计", "cmd": "display interface",
        "purpose": ("%d 个接口存在错误包，累计 %d 个" % (err_ports or 0, err_total or 0))
                   if err_total else ("无接口错误包" if insp else "尚未采集接口错包"),
        "ok": None if insp.get("error_total") is None else (not err_total or err_total == 0)})
    checks.append({
        "item": "生成树（STP）状态", "cmd": "display stp / display stp brief",
        "purpose": ("STP %s · 模式 %s · 转发口 %s · 阻塞口 %s"
                    % (stp_text, insp.get("stp_mode") or "—",
                       insp.get("stp_forward") if insp.get("stp_forward") is not None else "—",
                       insp.get("stp_blocked") if insp.get("stp_blocked") is not None else "—"))
                   if insp else "尚未采集 STP 状态",
        "ok": None if not insp else (stp_state != "disabled")})
    checks.append({
        "item": "巡检结论", "cmd": COLLECT_CMD_LABEL,
        "purpose": (insp.get("issues") or "巡检判定正常，未记录异常项") if insp else "尚未巡检",
        "ok": None if not insp else bool(insp.get("healthy"))})
    checks.append({
        "item": "指标采集", "cmd": COLLECT_CMD_LABEL,
        "purpose": ("最近采集 %s%s" % (nz.fmt_time(mon.get("collected_at")),
                                       "" if mon.get("ok") else "（采集失败：%s）"
                                       % (mon.get("error") or "原因未记录")))
                   if mon else "尚无 SNMP 采集记录",
        "ok": None if not mon else bool(mon.get("ok"))})
    checks.append({
        "item": "LLDP 邻居", "cmd": "display lldp neighbor",
        "purpose": ("发现 %d 个邻居（已识别 %d 个）"
                    % (len(lldp), len([x for x in lldp if x.get("known_device")])))
                   if lldp else "未采集到 LLDP 邻居",
        # 未识别的邻居说明台账缺设备，不应把该项判为通过。
        "ok": None if not lldp else any(x.get("known_device") for x in lldp)})
    checks.append({
        "item": "配置备份", "cmd": "SSH 采集 current-configuration",
        "purpose": ("已归档 %d 份配置，最近 %s" % (len(backups), backups[0].get("name", ""))
                    if backups else "尚无该设备的配置备份"),
        "ok": None if not backups else True})
    checks.append({
        "item": "告警与事件", "cmd": "本平台采集判定",
        "purpose": ("近 90 天 %d 条告警" % len(alerts)) if alerts else "无告警记录",
        "ok": None if not alerts else not any(
            (a.get("status") or "") not in ("resolved", "closed") for a in alerts)})
    checks.append({
        "item": "巡检时点", "cmd": COLLECT_CMD_LABEL,
        "purpose": ("最近巡检 %s" % nz.fmt_time(insp.get("inspected_at"))) if insp else "尚未巡检",
        "ok": None if not insp else True})
    for item in checks:
        label, tone = _result_tag(item.get("ok"))
        item["result"] = label
        item["tone"] = tone
    return checks


def _security_checks(dev: dict, insp: dict | None, mon: dict | None,
                     alerts: list, backups: list) -> list:
    """安全设备检查项：复用可采集的通用指标，并单列策略/HA/特征库现场口径。"""
    base = _switch_checks(dev, insp, mon, [], alerts, backups)
    keep = []
    for check in base:
        if check.get("item") in ("生成树（STP）状态", "LLDP 邻居"):
            continue
        keep.append(check)
    extra = [
        {"item": "安全策略基线", "cmd": "display security-policy / show policy",
         "purpose": "需按厂商命令或安全策略基线核查；未采集到策略命中与冗余策略数据",
         "ok": None},
        {"item": "HA / 双机热备", "cmd": "display hrp state / show high-availability",
         "purpose": "需确认主备状态、心跳链路与配置同步结果；未采集",
         "ok": None},
        {"item": "特征库 / 规则库", "cmd": "display update status / show signature",
         "purpose": "需确认 IPS/AV/URL 等特征库版本与更新时间；未采集",
         "ok": None},
        {"item": "会话与并发", "cmd": "display firewall session table / show session",
         "purpose": "需结合业务基线确认会话数与新建速率；未采集",
         "ok": None},
    ]
    for item in extra:
        label, tone = _result_tag(item.get("ok"))
        item["result"] = label
        item["tone"] = tone
    return keep + extra

def _server_checks(dev: dict, insp: dict | None, mon: dict | None,
                   alerts: list, backups: list, metrics: list) -> list:
    insp = insp or {}
    mon = mon or {}
    cpu = _num(insp.get("cpu")) if insp.get("cpu") is not None else _num(mon.get("cpu"))
    mem = _num(insp.get("memory")) if insp.get("memory") is not None else _num(mon.get("memory"))
    disk = nz.metric_value(metrics, dev.get("id"), ("disk", "磁盘", "filesystem"))
    temp = nz.metric_value(metrics, dev.get("id"), ("temp", "温度"))
    checks = [
        {"item": "主机在线状态", "ok": bool(dev.get("online")),
         "note": "最近在线 %s" % (nz.fmt_time(dev.get("last_online_at")) or "未记录")},
        {"item": "操作系统 / 版本", "ok": bool(dev.get("version")),
         "note": dev.get("version") or "尚未采集到系统版本"},
        {"item": "CPU 平均利用率", "ok": None if cpu is None else cpu < nz.CPU_WARN_PCT,
         "note": ("均值 %.0f%%，%s" % (cpu, "低于 80% 告警阈值" if cpu < nz.CPU_WARN_PCT
                                      else "已达告警阈值"))
                 if cpu is not None else "未采集到 CPU 指标"},
        {"item": "内存平均利用率", "ok": None if mem is None else mem < nz.MEM_WARN_PCT,
         "note": ("均值 %.0f%%，%s" % (mem, "低于 80% 告警阈值" if mem < nz.MEM_WARN_PCT
                                      else "已达告警阈值"))
                 if mem is not None else "未采集到内存指标"},
        {"item": "磁盘使用情况", "ok": None if disk is None else disk < 90,
         "note": ("使用率 %.0f%%" % disk) if disk is not None else "未采集到磁盘指标"},
        {"item": "机箱温度", "ok": None if temp is None else temp < 50,
         "note": ("当前 %.1f℃" % temp) if temp is not None else "未采集到温度传感器"},
        {"item": "告警检查", "ok": None if not alerts else not any(
            (a.get("status") or "") not in ("resolved", "closed") for a in alerts),
         "note": ("近 90 天 %d 条告警" % len(alerts)) if alerts else "无告警记录"},
        {"item": "配置 / 数据备份", "ok": None if not backups else True,
         "note": ("已归档 %d 份" % len(backups)) if backups else "尚无备份记录"},
        {"item": "巡检结论", "ok": None if not insp else bool(insp.get("healthy")),
         "note": (insp.get("issues") or "巡检判定正常") if insp else "尚未巡检"},
        {"item": "采集时点", "ok": None if not (insp or mon) else True,
         "note": nz.fmt_time(insp.get("inspected_at") or mon.get("collected_at")) or "尚未采集"},
        {"item": "健康度评分", "ok": True,
         "note": "%.1f / 100（平台口径：巡检结论 + CPU/内存阈值 + 接口错包 + 在线状态）"
                 % (dev.get("health_score") or 0)},
    ]
    for item in checks:
        label, tone = _result_tag(item.get("ok"))
        item["result"] = label
        item["tone"] = tone
    return checks


def health_page(kind: str, key=None) -> dict:
    """服务器 / 交换机健康检查页的数据包。"""
    devices, source, info = devices_view()
    wanted = kind if kind in ("server", "switch", "security") else "switch"
    pool = [d for d in devices if d["group_kind"] == wanted]
    dev = _find_device(pool, key)
    if dev is None:
        return {"device": None, "pool": pool, "source": source, "source_info": info}
    inspections, _, _ = fetch("inspections")
    monitors, _, _ = fetch("monitors")
    metrics, _, _ = fetch("metrics")
    alerts, _, _ = fetch("alerts", hours=24 * 90)
    backups_all, _, _ = fetch("backups")
    own_insp = sort_desc([r for r in inspections
                          if _belongs_to_device(r, dev)],
                         "inspected_at")
    own_mon = sort_desc([r for r in monitors
                         if _belongs_to_device(r, dev)],
                        "collected_at")
    own_alerts = sort_desc([a for a in alerts
                            if _belongs_to_device(a, dev)], "triggered_at")
    own_backups = [b for b in backups_all
                   if (b.get("device_ip") or "") == dev["ip"]]
    own_metrics = [m for m in metrics
                   if _belongs_to_device(m, dev)]
    insp = own_insp[0] if own_insp else None
    mon = own_mon[0] if own_mon else None
    ledger = dev.get("ledger") or {}
    lldp = _lldp_of(dev, insp) if wanted == "switch" else []
    if lldp:
        known = {str(p.get("name") or "").strip().lower() for p in pool}
        known |= {str(p.get("ip") or "").strip() for p in pool}
        for row in lldp:
            row["known_device"] = (row.get("neighbor_name") or "").lower() in known \
                or (row.get("neighbor_ip") or "") in known

    basic = [
        {"label": "设备名称", "value": dev["name"]},
        {"label": "设备型号", "value": dev["model"] or "—"},
        {"label": "操作系统" if wanted == "server" else ("软件版本" if wanted == "switch" else "系统 / 软件版本"),
         "value": dev["version"] or "—"},
        {"label": "IP 地址", "value": dev["ip"]},
        {"label": "资产编号", "value": ledger.get("asset_no") or "—"},
        {"label": "责任人", "value": ledger.get("owner") or "—"},
        {"label": "设备用途", "value": ledger.get("usage") or "—"},
        {"label": "设备地点", "value": ledger.get("location") or dev.get("group") or "—"},
        {"label": "巡检周期", "value": _period_label(24 * 7)},
        {"label": "最近巡检", "value": nz.fmt_time(insp.get("inspected_at")) if insp else "尚未巡检"},
    ]

    if wanted == "server":
        perf = [
            {"name": "CPU 平均利用率",
             "value": ("%.0f%%" % dev["cpu"]) if dev.get("cpu") is not None else "未采集"},
            {"name": "内存平均利用率",
             "value": ("%.0f%%" % dev["memory"]) if dev.get("memory") is not None else "未采集"},
            {"name": "磁盘使用率",
             "value": ("%.0f%%" % nz.metric_value(metrics, dev["id"], ("disk", "磁盘")))
                      if nz.metric_value(metrics, dev["id"], ("disk", "磁盘")) is not None
                      else "未采集"},
        ]
        env = [
            {"name": "机箱温度",
             "value": ("%.1f℃" % nz.metric_value(metrics, dev["id"], ("temp", "温度")))
                      if nz.metric_value(metrics, dev["id"], ("temp", "温度")) is not None
                      else "未采集"},
            {"name": "连通状态", "value": "在线可管理" if dev["online"] else "不可达"},
            {"name": "最近在线", "value": nz.fmt_time(dev.get("last_online_at")) or "未记录"},
        ]
        apps = [
            {"name": "采集方式", "value": "SSH 只读采集（系统信息 / 资源 / 服务 / 日志）"},
            {"name": "遥测指标条数", "value": "%d 条" % len(own_metrics)},
            {"name": "SNMP 采集", "value": ("最近 %s" % nz.fmt_time(mon.get("collected_at")))
                      if mon else "无记录"},
        ]
        return {"device": dev, "pool": pool, "source": source, "source_info": info,
                "basic": basic, "checks": _server_checks(dev, insp, mon, own_alerts,
                                                         own_backups, metrics),
                "resources": perf, "environment": env, "applications": apps,
                "advice": _advice(dev, insp, own_alerts)}

    perf = [
        {"name": "CPU 利用率",
         "value": ("%.0f%%" % dev["cpu"]) if dev.get("cpu") is not None else "未采集"},
        {"name": "内存利用率",
         "value": ("%.0f%%" % dev["memory"]) if dev.get("memory") is not None else "未采集"},
        {"name": "接口错包",
         "value": ("%d 个 / 累计 %s" % (insp.get("error_ports") or 0,
                                       insp.get("error_total") or 0)) if insp
                  else "未采集"},
    ]
    if wanted == "switch":
        perf.append({
            "name": "STP 端口",
            "value": ("转发 %s · 阻塞 %s" % (insp.get("stp_forward") if insp else "—",
                                            insp.get("stp_blocked") if insp else "—"))
                     if insp else "未采集",
        })
    status_rows = [
        {"name": "设备在线状态", "value": "在线" if dev["online"] else "离线",
         "tone": "success" if dev["online"] else "danger"},
        {"name": "SNMP 采集状态",
         "value": ("正常" if mon.get("ok") else "失败") if mon else "无记录",
         "tone": ("success" if mon.get("ok") else "danger") if mon else "muted"},
        {"name": "配置备份",
         "value": ("%d 份" % len(own_backups)) if own_backups else "无记录",
         "tone": "success" if own_backups else "muted"},
        {"name": "未恢复告警",
         "value": "%d 条" % len([a for a in own_alerts
                                 if (a.get("status") or "") not in ("resolved", "closed")]),
         "tone": "warning" if own_alerts else "success"},
    ]
    checks = (_server_checks(dev, insp, mon, own_alerts, own_backups, own_metrics)
              if wanted == "server" else
              (_security_checks(dev, insp, mon, own_alerts, own_backups)
               if wanted == "security" else
               _switch_checks(dev, insp, mon, lldp, own_alerts, own_backups)))
    return {"device": dev, "pool": pool, "source": source, "source_info": info,
            "basic": basic,
            "checks": checks,
            "performance": perf, "status_rows": status_rows,
            "neighbors": [{
                "local_port": x.get("local_port") or "",
                "neighbor_name": x.get("neighbor_name") or "",
                "neighbor_port": x.get("neighbor_port") or "",
                "neighbor_ip": x.get("neighbor_ip") or "",
                "known": bool(x.get("known_device")),
            } for x in lldp],
            "advice": _advice(dev, insp, own_alerts)}


# ------------------------------------------------------------------ 告警 / 巡检 / 备份
SEVERITY_RANK = {"critical": 4, "major": 3, "warning": 2, "info": 1, "debug": 0}


def _alert_family(item: dict) -> str:
    key = str(item.get("dedupe_key") or item.get("metric") or "").strip().lower()
    if key:
        return re.split(r"[:|]", key, maxsplit=1)[0]
    text = str(item.get("content") or item.get("rule") or "alert")
    return re.sub(r"\d+(?:\.\d+)?", "#", text).strip().lower()


def _alert_is_open(item: dict) -> bool:
    return (item.get("status") or "").lower() not in ("resolved", "closed")


def aggregate_alerts(rows: list) -> list:
    """同设备、同指标族的告警收敛为一条，保留次数/级别/首次与最近时间。"""
    groups: dict = {}
    for item in rows:
        ip = item.get("device_ip") or item.get("device") or ""
        family = _alert_family(item)
        key = "%s|%s" % (ip, family)
        sev = nz.severity_view(item.get("severity"))[0]
        stamp = str(item.get("triggered_at") or "")
        group = groups.get(key)
        content = item.get("content") or item.get("rule") or "告警"
        if not group:
            group = {
                "key": key, "device": item.get("device") or ip, "device_ip": ip,
                "metric": item.get("metric") or family,
                "family": family,
                "change": nz.is_change_metric(item.get("metric")),
                "change_label": nz.change_metric_label(item.get("metric")),
                "severity": sev, "severity_label": nz.severity_view(sev)[1],
                "status": item.get("status_display") or item.get("status") or "未知",
                "open": _alert_is_open(item),
                "count": 0, "resource_keys": set(), "recent": [], "alert_ids": [],
                "latest_id": item.get("id"), "first_at": stamp, "last_at": stamp,
                "first_time": nz.fmt_time(stamp), "last_time": nz.fmt_time(stamp),
                "title": content, "latest_content": content,
                "value": item.get("value"),
            }
            groups[key] = group
        group["count"] += 1
        if item.get("id") is not None:
            group["alert_ids"].append(item.get("id"))
        resource = item.get("dedupe_key") or item.get("metric") or content
        group["resource_keys"].add(str(resource))
        if SEVERITY_RANK.get(sev, 0) > SEVERITY_RANK.get(group["severity"], 0):
            group["severity"] = sev
            group["severity_label"] = nz.severity_view(sev)[1]
        if _alert_is_open(item):
            group["open"] = True
            group["status"] = item.get("status_display") or item.get("status") or "未恢复"
        if not group["first_at"] or (stamp and stamp < group["first_at"]):
            group["first_at"] = stamp
            group["first_time"] = nz.fmt_time(stamp)
        if stamp >= group["last_at"]:
            group["last_at"] = stamp
            group["last_time"] = nz.fmt_time(stamp)
            group["latest_content"] = content
            group["title"] = content
            group["value"] = item.get("value")
            group["latest_id"] = item.get("id")
            group["status"] = item.get("status_display") or item.get("status") or group["status"]
        if len(group["recent"]) < 6:
            group["recent"].append({
                "time": nz.fmt_time(stamp), "severity": nz.severity_view(item.get("severity"))[1],
                "content": content,
                "status": item.get("status_display") or item.get("status") or "",
            })
    out = []
    for group in groups.values():
        group["resource_count"] = len(group.pop("resource_keys"))
        group["recent"].sort(key=lambda x: x.get("time") or "", reverse=True)
        out.append(group)
    out.sort(key=lambda x: (not x.get("open"), x.get("last_at") or ""), reverse=True)
    return out

def alert_board(hours: int = 24 * 30, severity: str = "", status: str = "",
                device: str = "", source_key: str = "", keyword: str = "",
                limit: int = 100) -> dict:
    rows, source, info = fetch("alerts", hours=hours)
    filtered = []
    kw = (keyword or "").strip().lower()
    for item in rows:
        if severity and nz.severity_view(item.get("severity"))[0] != severity.lower():
            continue
        if status and (item.get("status") or "").lower() != status.lower():
            continue
        if device and device.lower() not in ((item.get("device") or "") + (item.get("device_ip") or "")).lower():
            continue
        if source_key and (item.get("source") or "").lower() != source_key.lower():
            continue
        if kw and kw not in " ".join(str(item.get(k) or "") for k in
                                      ("device", "device_ip", "content", "metric", "rule")).lower():
            continue
        filtered.append(item)
    severity_count = {"critical": 0, "major": 0, "warning": 0, "info": 0}
    for item in rows:
        key = nz.severity_view(item.get("severity"))[0]
        severity_count[key] = severity_count.get(key, 0) + 1
    status_count: dict = {}
    for item in rows:
        key = item.get("status_display") or item.get("status") or "未知"
        status_count[key] = status_count.get(key, 0) + 1
    groups = aggregate_alerts(filtered)
    group_severity = {"critical": 0, "major": 0, "warning": 0, "info": 0}
    group_status: dict = {}
    device_groups: dict = {}
    for group in groups:
        group_severity[group["severity"]] = group_severity.get(group["severity"], 0) + 1
        key = "未恢复" if group.get("open") else (group.get("status") or "已恢复")
        group_status[key] = group_status.get(key, 0) + 1
        bucket = device_groups.setdefault(group.get("device_ip") or group.get("device"), {
            "device": group.get("device") or group.get("device_ip") or "",
            "device_ip": group.get("device_ip") or "", "groups": 0, "alerts": 0,
        })
        bucket["groups"] += 1
        bucket["alerts"] += group.get("count") or 0
    return {
        "source": source, "source_info": info, "total": len(filtered),
        "raw_total": len(filtered), "group_total": len(groups),
        "collapsed": max(0, len(filtered) - len(groups)),
        "collapse_rate": round(100.0 * max(0, len(filtered) - len(groups)) / len(filtered), 1)
                         if filtered else 0.0,
        "by_severity": severity_count, "by_status": status_count,
        "group_by_severity": group_severity, "group_by_status": group_status,
        "by_device": sorted(device_groups.values(), key=lambda x: x["alerts"], reverse=True),
        "groups": groups[:limit],
        "cards": [{
            "id": item.get("id"),
            "title": item.get("content") or item.get("rule") or "告警",
            "source": item.get("source_display") or item.get("source") or "",
            "severity": nz.severity_view(item.get("severity"))[0],
            "severity_label": nz.severity_view(item.get("severity"))[1],
            "severity_raw": item.get("severity") or "",
            "status": item.get("status_display") or item.get("status") or "",
            "device": item.get("device") or "",
            "device_ip": item.get("device_ip") or "",
            "metric": item.get("metric") or "",
            "change": nz.is_change_metric(item.get("metric")),
            "change_label": nz.change_metric_label(item.get("metric")),
            "value": item.get("value"),
            "time": nz.fmt_time(item.get("triggered_at")),
        } for item in filtered[:limit]],
    }


def inspection_rows(hours: int = 24 * 90, limit: int = 200, kind: str = "") -> dict:
    rows, source, info = fetch("inspections", hours=hours)
    devices, _, _ = devices_view()
    kind_of = {d["id"]: d["group_kind"] for d in devices}
    name_of = {d["id"]: d for d in devices}
    items = []
    for rec in rows:
        group = kind_of.get(rec.get("device_id"), "other")
        if kind and group != kind:
            continue
        dev = name_of.get(rec.get("device_id"), {})
        result = nz.health(dev or {"online": True}, rec, {})
        items.append({
            "id": rec.get("id"), "run_id": rec.get("run_id"),
            "device": rec.get("device") or dev.get("name") or "",
            "device_ip": rec.get("device_ip") or dev.get("ip") or "",
            "type": dev.get("type_label") or "—",
            "group": group,
            "owner": (dev.get("ledger") or {}).get("owner") or "—",
            "asset_no": (dev.get("ledger") or {}).get("asset_no") or "—",
            "usage": (dev.get("ledger") or {}).get("usage") or "—",
            "location": (dev.get("ledger") or {}).get("location") or "—",
            "cpu": rec.get("cpu"), "memory": rec.get("memory"),
            "healthy": bool(rec.get("healthy")),
            "issues": rec.get("issues") or "",
            "score": result["score"], "label": result["label"],
            "tone": result["tone"],
            "time": nz.fmt_time(rec.get("inspected_at")),
            "inspected_at": rec.get("inspected_at") or "",
        })
    items.sort(key=lambda r: r["inspected_at"], reverse=True)
    return {"source": source, "source_info": info, "total": len(items),
            "rows": items[:limit]}


def _safe_filename(text: str) -> str:
    """设备名 → 安全的文件名（保留中文、字母数字与 -_.）。"""
    out = []
    for ch in str(text or ""):
        out.append(ch if (ch.isalnum() or ch in "-_.()（）") else "_")
    return "".join(out).strip("._")[:80]


def _safe_zip_part(text: str) -> str:
    """单个 ZIP 路径片段：保留中文、字母数字与常见安全符号。"""
    return _safe_filename(str(text or "").replace("\\", "_").replace("/", "_"))


def _safe_zip_relpath(path: str) -> str:
    """服务器备份相对路径 → 安全 ZIP 路径；去掉 . / ..，防止目录穿越。"""
    parts = []
    for piece in str(path or "").replace("\\", "/").split("/"):
        piece = piece.strip()
        if not piece or piece in (".", ".."):
            continue
        safe = _safe_zip_part(piece)
        if safe:
            parts.append(safe)
    return "/".join(parts)


def package_configs(device_key: str = "") -> tuple:
    """实时读取设备配置/备份并在内存中打包成 ZIP（不写服务器磁盘）。

    * 交换机：执行 display current-configuration（dis cu），每台一个"设备名.cfg"；
    * 服务器：SSH/SFTP 进入采集设置里的备份目录，保留原始文件，
      统一放在"设备名/"目录下，绝不把多台设备拼成一个文本；
    * 所有文件只在内存中合成一个 ZIP，由浏览器直接下载。
    """
    import concurrent.futures
    import io
    import socket
    import zipfile

    from . import remote as remote_login
    from .collect import runner as collect_runner
    from .collect import server as server_collector

    devices, source, _info = devices_view()
    key = (device_key or "").strip()
    pool = []
    seen = set()
    for dev in devices:
        ip = str(dev.get("ip") or "").strip()
        if not ip or ip in seen:
            continue
        if key and str(dev.get("id")) != key and ip != key:
            continue
        seen.add(ip)
        pool.append(dev)
    if not pool:
        raise ValueError("没有可打包的设备")

    conf = collect_runner.settings()
    timeout = max(20.0, min(60.0, float(conf.get("timeout") or 25)))
    concurrency = max(1, min(12, max(int(conf.get("concurrency") or 5), len(pool))))
    backup_paths = {
        "linux": conf.get("server_backup_path_linux") or "",
        "windows": conf.get("server_backup_path_windows") or "",
    }

    def one(dev: dict) -> dict:
        ip = dev.get("ip") or ""
        name = dev.get("name") or ip
        profile = collect_runner.profile_of(dev)
        client = session = None
        try:
            cred = remote_login.credential_get(ip)
            if not cred:
                raise collect_runner.CollectError("没有配置 SSH 登录凭据")
            port = int(cred.get("port") or dev.get("port") or 22)
            probe_timeout = min(3.0, timeout)
            try:
                with socket.create_connection((ip, port), timeout=probe_timeout):
                    pass
            except Exception as exc:                    # noqa: BLE001
                return {"name": name, "ip": ip, "ok": False, "kind": profile,
                        "files": [], "errors": [], "unreachable": True,
                        "error": "SSH 端口 %d 不可达（%.1f 秒预检）：%s"
                                 % (port, probe_timeout, type(exc).__name__)}
            client = collect_runner._connect(ip, timeout)
            if profile == "server":
                os_type = server_collector.detect_os(
                    client, timeout, str(dev.get("os_type") or ""))
                path = backup_paths.get(os_type) or ""
                info = server_collector.read_backup_files(
                    client, os_type, path, timeout)
                if not info["files"]:
                    detail = "；".join(info.get("errors") or []) or "备份目录为空"
                    raise collect_runner.CollectError("未找到可下载的备份文件：" + detail[:240])
                return {"name": name, "ip": ip, "ok": True, "kind": "server",
                        "files": info["files"], "errors": info.get("errors") or [],
                        "remote_path": info.get("path") or path, "error": ""}
            if not collect_runner.is_supported(dev):
                raise collect_runner.CollectError("非华为 VRP 设备，无法执行 dis cu")
            session = collect_runner.VrpSession(client, timeout)
            session.run("screen-length 0 temporary")
            text = session.run("display current-configuration")
            if not (text or "").strip():
                raise collect_runner.CollectError("dis cu 命令回显为空")
            return {"name": name, "ip": ip, "ok": True, "kind": "switch",
                    "files": [{"path": name + ".cfg",
                               "data": text.encode("utf-8")}],
                    "errors": [], "error": ""}
        except Exception as exc:                        # noqa: BLE001
            return {"name": name, "ip": ip, "ok": False, "kind": profile,
                    "files": [], "errors": [], "error": str(exc)[:400]}
        finally:
            try:
                if session is not None:
                    session.close()
                elif client is not None:
                    client.close()
            except Exception:                           # noqa: BLE001
                pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as workers:
        results = list(workers.map(one, pool))

    errors = ["%s(%s): %s" % (r["name"], r["ip"], r["error"])
              for r in results if not r.get("ok")]
    if not any(r.get("ok") for r in results):
        unreachable = [r for r in results if r.get("unreachable")]
        no_cred = [r for r in results if "没有配置 SSH 登录凭据" in str(r.get("error") or "")]
        if len(unreachable) == len(results):
            reason = ("所有设备的 SSH 端口均不可达。请确认设备在线、管理地址和端口正确，"
                      "并已完成 SSH 凭据配置；如果当前仍是演示地址，请先在设备清单中录入真实设备。")
        elif len(no_cred) == len(results):
            reason = "所有设备都还没有配置 SSH 登录凭据，请先在设备台账里填写账号和口令/私钥。"
        else:
            reason = "；".join(errors[:4]) or "没有读取到任何配置或备份文件"
        raise ValueError("没有可下载的文件：" + reason[:600])

    def unique_base(name: str, ip: str, used: set) -> str:
        base = _safe_filename(name) or ip.replace(".", "_").replace(":", "_") or "device"
        candidate = base
        index = 2
        while candidate.lower() in used:
            candidate = "%s-%d" % (base, index)
            index += 1
        used.add(candidate.lower())
        return candidate

    buffer = io.BytesIO()
    used_names = set()
    used_arcnames = set()
    ok = failed = file_count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for row in results:
            if not row.get("ok"):
                failed += 1
                continue
            base = unique_base(row["name"], row["ip"], used_names)
            if row["kind"] == "switch":
                arcname = base + ".cfg"
                archive.writestr(arcname, row["files"][0]["data"])
                used_arcnames.add(arcname.lower())
                file_count += 1
                ok += 1
                continue
            added = 0
            for item in row.get("files") or []:
                rel = _safe_zip_relpath(item.get("path") or "")
                if not rel:
                    continue
                arcname = base + "/" + rel
                if arcname.lower() in used_arcnames:
                    stem, dot, ext = arcname.rpartition(".")
                    suffix = 2
                    while arcname.lower() in used_arcnames:
                        if dot:
                            arcname = "%s-%d%s%s" % (stem, suffix, dot, ext)
                        else:
                            arcname = "%s-%d" % (ext, suffix)
                        suffix += 1
                archive.writestr(arcname, item.get("data") or b"")
                used_arcnames.add(arcname.lower())
                added += 1
            if added:
                file_count += added
                ok += 1
            else:
                failed += 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return ("配置备份-%s.zip" % stamp, buffer.getvalue(),
            {"ok": ok, "failed": failed, "total": len(results),
             "files": file_count, "source": source})

def backup_overview(keyword: str = "", page: int = 1, page_size: int = 20) -> dict:
    files, source, info = fetch("backups")
    devices, _, _ = devices_view()
    rows = []
    for item in _normalize_backups({"files": files}):
        rows.append({
            "name": item.get("name") or item.get("filename") or "",
            "device_ip": item.get("device_ip") or item.get("ip") or "",
            "size": item.get("size") or 0,
            "size_text": _human_size(item.get("size") or 0),
            "mtime": item.get("mtime") or item.get("modified") or "",
            "time_text": nz.fmt_time(item.get("mtime") or item.get("modified")),
        })
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    all_rows = rows
    kw = (keyword or "").strip().lower()
    if kw:
        rows = [r for r in rows
                if kw in (r["name"] + " " + r["device_ip"]).lower()]
    page_size = max(1, int(page_size or 20))
    page = max(1, int(page or 1))
    total = len(rows)
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, pages)
    rows = rows[(page - 1) * page_size: page * page_size]
    covered = len({r["device_ip"] for r in all_rows if r["device_ip"]})
    total_size = sum(r["size"] for r in all_rows)
    has_backup = set([r["device_ip"] for r in all_rows if r["device_ip"]])
    coverage = [{"name": d["name"], "ip": d["ip"], "type": d["type_label"]}
                for d in devices if d["ip"] not in has_backup]
    return {
        "source": source, "source_info": info,
        "files": rows, "total": total, "page": page, "page_size": page_size,
        "pages": pages, "keyword": keyword,
        "file_count": len(all_rows),
        "total_size": total_size, "total_size_text": _human_size(total_size),
        "devices_total": len(devices), "devices_covered": covered,
        "coverage": coverage,
        "newest": all_rows[0]["time_text"] if all_rows else "",
    }


# ------------------------------------------------------------------ 台账补充（批量）
LEDGER_COLUMNS = ["ip", "asset_no", "owner", "usage", "location",
                  "warranty_until", "kind_override", "note"]
KIND_KEYS = ("switch", "core_switch", "aggregation_switch", "access_switch",
             "router", "firewall", "waf", "ips", "vpn", "security", "ac",
             "server", "other")


def ledger_export() -> dict:
    """台账（设备字段 + 台账补充字段）导出用数据。"""
    devices, source, info = devices_view()
    rows = []
    for dev in devices:
        ledger = dev.get("ledger") or {}
        rows.append({
            "ip": dev["ip"], "name": dev["name"], "type_label": dev["type_label"],
            "model": dev["model"], "vendor": dev["vendor_display"],
            "serial": dev["serial"], "version": dev["version"],
            "group": dev["group"], "region": dev["region"],
            "online": "在线" if dev["online"] else "离线",
            "last_inspected_text": dev["last_inspected_text"] or "尚未巡检",
            "health_score": dev["health_score"], "health_label": dev["health_label"],
            "asset_no": ledger.get("asset_no") or "",
            "owner": ledger.get("owner") or "",
            "usage": ledger.get("usage") or "",
            "location": ledger.get("location") or "",
            "warranty_until": ledger.get("warranty_until") or "",
            "kind_override": ledger.get("kind_override") or "",
            "note": ledger.get("note") or "",
            "updated_at": ledger.get("updated_at") or "",
        })
    return {"source": source, "source_info": info, "rows": rows, "total": len(rows)}


def _ledger_row_normalize(raw: dict) -> dict:
    """把一行 CSV 的列名归一到标准字段（中英混用、空格差异都认）。"""
    # 设备身份列（清单页展示用）在导入时一律忽略：模板里它们是只读信息，
    # 尤其「设备类型（只读）」不能当成「类型纠正」写回去。
    ignore_keywords = ("只读", "序号", "设备名称", "主机名", "品牌型号", "型号",
                       "系统版本", "软件版本", "所在分组", "分组", "地区",
                       "在线状态", "健康状态", "健康度")
    key_map = {
        "ip": "ip", "ip地址": "ip", "ip 地址": "ip", "设备ip": "ip", "设备 ip": "ip",
        "管理ip": "ip", "地址": "ip",
        "asset_no": "asset_no", "资产编号": "asset_no", "资产号": "asset_no",
        "owner": "owner", "责任人": "owner", "负责人": "owner", "运维责任人": "owner",
        "usage": "usage", "用途": "usage", "设备用途": "usage",
        "location": "location", "地点": "location", "设备地点": "location",
        "位置": "location", "所在位置": "location",
        "warranty_until": "warranty_until", "维保到期": "warranty_until",
        "维保到期日": "warranty_until", "保修到期": "warranty_until",
        "kind_override": "kind_override", "类型纠正": "kind_override",
        "设备类型": "kind_override", "类型": "kind_override",
        "note": "note", "备注": "note", "说明": "note",
    }
    out: dict = {}
    for key, value in (raw or {}).items():
        if not key:
            continue
        header = str(key).strip()
        if any(word in header for word in ignore_keywords):
            continue
        canonical = key_map.get(header.lower()) or key_map.get(header)
        if canonical:
            out[canonical] = (value or "").strip() if isinstance(value, str) else value
    return out


#: 文档示例地址（RFC 5737）——模板里的示例行用这些，导入时直接忽略
EXAMPLE_IPS = ("192.0.2.", "198.51.100.", "203.0.113.", "10.0.0.254")


def _is_example_row(ip: str, row: dict) -> bool:
    """判断是不是模板自带的示例行（保留地址，或任意单元格写了「示例」）。"""
    if any(str(ip).startswith(prefix) for prefix in EXAMPLE_IPS):
        return True
    return any("示例" in str(value or "") for value in row.values())


def ledger_import(text: str, operator: str = "admin", dry_run: bool = False,
                  clear_empty: bool = False) -> dict:
    """按 IP 批量导入台账补充字段（CSV：首行表头；支持中英文列名）。

    * 只写本平台自己的库，所以「导入台账」在实景里也是安全的；
    * `dry_run=True` 只做预检：逐行给出「新增 / 更新 / 跳过 / 报错」与将要写入的字段，不落库。
    """
    import csv
    import io as _io

    devices, _, _ = devices_view()
    by_ip = {d["ip"]: d for d in devices}
    store = get_store()
    reader = csv.DictReader(_io.StringIO((text or "").lstrip("\ufeff")))
    created = updated = 0
    errors: list[str] = []
    details: list[dict] = []
    seen = set()
    for index, raw in enumerate(reader, start=2):
        row = _ledger_row_normalize(raw)
        ip = row.get("ip") or ""
        if not ip and not any(row.values()):
            continue                                  # 整行空白，直接跳过
        if not ip:
            errors.append("第 %d 行：缺少 IP 列" % index)
            details.append({"line": index, "ip": "", "action": "error",
                            "message": "缺少 IP 列"})
            continue
        if ip in seen:
            errors.append("第 %d 行：同一文件里 IP %s 重复" % (index, ip))
            details.append({"line": index, "ip": ip, "action": "error",
                            "message": "同一文件里 IP 重复（只保留第一条）"})
            continue
        seen.add(ip)
        dev = by_ip.get(ip)
        if dev is None and _is_example_row(ip, row):
            details.append({"line": index, "ip": ip, "action": "skip",
                            "message": "模板里的示例行，已自动忽略"})
            continue
        if dev is None:
            errors.append("第 %d 行：%s 不在设备台账里" % (index, ip))
            details.append({"line": index, "ip": ip, "action": "error",
                            "message": "不在设备台账里（先在「设备清单」新增该设备）"})
            continue

        kind = row.get("kind_override") or ""
        if kind and kind not in KIND_KEYS and kind not in nz.KIND_LABELS.values():
            errors.append("第 %d 行：设备类型「%s」不认识" % (index, kind))
            details.append({"line": index, "ip": ip, "action": "error",
                            "message": "设备类型「%s」不认识（可用：%s）"
                                       % (kind, "、".join(KIND_KEYS))})
            continue
        if kind and kind in nz.KIND_LABELS.values():   # 允许直接写中文类型
            kind = [k for k, v in nz.KIND_LABELS.items() if v == kind][0]

        cells = {
            "asset_no": row.get("asset_no", ""),
            "owner": row.get("owner", ""),
            "usage": row.get("usage", ""),
            "location": row.get("location", ""),
            "warranty_until": row.get("warranty_until", ""),
            "kind_override": kind,
            "note": row.get("note", ""),
        }
        current = store.ledger_get(ip)
        # 安全默认：空单元格=「本次不动这个字段」（避免模板原样导入把已有台账清空）；
        # 需要清空时把 clear_empty 打开。
        if clear_empty:
            target = dict(cells)
        else:
            target = {k: v for k, v in cells.items() if str(v or "").strip() != ""}
        if not target:
            details.append({"line": index, "ip": ip, "action": "skip", "name": dev["name"],
                            "message": "本行没有填任何台账字段（空值默认不改动）"})
            continue
        values = {"device_id": dev["id"], "device_name": dev["name"]}
        values.update(target)
        changed = [k for k, v in target.items()
                   if str(v or "") != str((current or {}).get(k) or "")]
        existed = bool(current)
        if not changed:
            details.append({"line": index, "ip": ip, "action": "skip",
                            "name": dev["name"], "message": "与现有台账一致，无需改动"})
            continue
        if dry_run:
            details.append({"line": index, "ip": ip, "action": "would_update",
                            "name": dev["name"],
                            "message": "将更新：" + "、".join(changed)})
            continue
        store.ledger_save(ip, values)
        if existed:
            updated += 1
            details.append({"line": index, "ip": ip, "action": "update",
                            "name": dev["name"],
                            "message": "已更新：" + "、".join(changed)})
        else:
            created += 1
            details.append({"line": index, "ip": ip, "action": "create",
                            "name": dev["name"],
                            "message": "新增台账：" + "、".join(changed)})
    if not dry_run:
        cache_clear()
        try:
            from . import auth
            auth.log_event(operator or "admin", "ledger_import",
                           "台账批量导入：新增 %d、更新 %d、跳过 %d、报错 %d"
                           % (created, updated,
                              len([d for d in details if d["action"] == "skip"]),
                              len(errors)))
        except Exception:                                   # noqa: BLE001
            pass
    skipped = len([d for d in details if d["action"] == "skip"])
    would = len([d for d in details if d["action"] == "would_update"])
    return {"ok": not errors or (created + updated + would) > 0,
            "dry_run": bool(dry_run), "clear_empty": bool(clear_empty),
            "created": created, "updated": updated, "skipped": skipped,
            "would_update": would, "errors": errors[:40],
            "error_count": len(errors), "total": created + updated + would,
            "details": details[:200], "operator": operator,
            "rows_parsed": len(details) + len([e for e in errors if "缺少 IP" in e])}


# 与「设备清单」页同一套信息段：前面是设备身份（台账 / 采集回填），
# 后面是台账补充（本平台可写）。模板与现状导出都用这一个口径。
LEDGER_IDENTITY_COLUMNS = [
    ("no", "序号"), ("name", "设备名称"), ("type_label", "设备类型（只读）"),
    ("model", "品牌型号"), ("version", "系统版本"), ("ip", "IP 地址"),
    ("group", "所在分组"), ("region", "地区"), ("online", "在线状态"),
    ("health_label", "健康状态"), ("health_score", "健康度"),
    ("last_inspected_text", "最近巡检"),
]
LEDGER_EDIT_COLUMNS = [
    ("asset_no", "资产编号"), ("owner", "责任人"), ("usage", "设备用途"),
    ("location", "设备地点"), ("warranty_until", "维保到期"),
    ("kind_override", "类型纠正"), ("note", "备注"),
]
LEDGER_CSV_COLUMNS = [key for key, _ in LEDGER_IDENTITY_COLUMNS] + \
                     [key for key, _ in LEDGER_EDIT_COLUMNS]
LEDGER_CSV_HEADERS = [title for _, title in LEDGER_IDENTITY_COLUMNS] + \
                     [title for _, title in LEDGER_EDIT_COLUMNS]
#: 旧版模板（只有 ip + 补充字段）仍然认，保持向后兼容
LEGACY_LEDGER_COLUMNS = ["ip", "asset_no", "owner", "usage", "location",
                         "warranty_until", "kind_override", "note"]


def _csv_cell(value) -> str:
    text = "" if value is None else str(value)
    if any(ch in text for ch in ',"\n'):
        text = '"' + text.replace('"', '""') + '"'
    return text


def ledger_csv_rows(include_values: bool = True) -> list:
    """台账 CSV 的数据行（身份列来自台账 / 采集回填，补充列来自本平台）。

    `include_values=False`（模板）：补充列留空，身份列照样填好，打开就能对号入座。
    """
    data = ledger_export()
    rows = []
    for index, row in enumerate(data["rows"], start=1):
        item = dict(row)
        item["no"] = index
        item["online"] = item.get("online") or ""
        line = []
        for key, _ in LEDGER_IDENTITY_COLUMNS:
            line.append(_csv_cell(item.get(key, "")))
        for key, _ in LEDGER_EDIT_COLUMNS:
            line.append(_csv_cell(item.get(key, "")) if include_values else "")
        rows.append(",".join(line))
    return rows


def ledger_csv_header() -> str:
    return ",".join(LEDGER_CSV_HEADERS)


def ledger_csv_example() -> str:
    """示例行：身份列用保留地址写，补充列给出填法（模板里带一行，可删）。"""
    identity = ["示例", "示例-交换机", "接入交换机（只读）", "H3C S5130S-28S-EI",
                "Comware V7", "192.0.2.10", "示例分组", "示例地区", "在线", "正常",
                "100", "2026.10.16 09:00"]
    edit = ["IT-0001", "张工", "楼层接入", "信息中心机房", "2027-12-31", "", "示例行：可删"]
    return ",".join([_csv_cell(v) for v in identity + edit])


def ledger_csv_export() -> str:
    """当前台账 → CSV（与导入模板同列同序，改完直接导回来）。"""
    lines = [ledger_csv_header()] + ledger_csv_rows(include_values=True)
    return "\n".join(lines) + "\n"


LEDGER_TEMPLATE = ("ip,asset_no,owner,usage,location,warranty_until,"
                   "kind_override,note\n"
                   "10.10.0.1,IT-0001,张工,核心交换,信息中心核心机房,2027-12-31,,主备双机\n")


def _normalize_backups(payload: dict) -> list:
    """备份条目 → 本平台统一结构。

    采集/备份目录给的是 `{name, ip, time_str, size, device_ip}`（不提供路径与正文），
    这里统一成 `{name, device_ip, size, mtime}`，页面与报表都用同一份结构。
    """
    items = (payload or {}).get("files") or (payload or {}).get("results") or []
    rows = []
    for item in items:
        rows.append({
            "name": item.get("name") or "",
            "device_ip": item.get("device_ip") or item.get("ip") or "",
            "size": item.get("size") or 0,
            "mtime": item.get("mtime") or item.get("time_str") or item.get("modified") or "",
        })
    return rows


def _human_size(size) -> str:
    try:
        size = float(size)
    except (TypeError, ValueError):
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return ("%.1f %s" % (size, unit)) if unit != "B" else ("%d B" % size)
        size /= 1024.0
    return "—"


def report_archive() -> dict:
    store = get_store()
    return {"exports": store.exports(limit=50),
            "templates": REPORT_TEMPLATES,
            "formats": ["xlsx", "csv", "docx", "pdf"]}


REPORT_TEMPLATES = [
    {"key": "inspection", "name": "网络设备巡检报告",
     "sheets": ["总览", "设备清单", "巡检明细"], "formats": ["xlsx", "csv"]},
    {"key": "server", "name": "服务器健康性检查报告",
     "sheets": ["服务器信息", "检查项", "资源指标"], "formats": ["xlsx", "csv", "docx", "pdf"],
     "doc": "版式报告：封面 / 机房环境 / 设备列表 / 评估项 / 现场巡检表 / "
            "逐条命令回显截图 / 数据分析 / 维护建议"},
    {"key": "switch", "name": "内网交换机健康性检查报告",
     "sheets": ["交换机信息", "检查项", "性能与邻居"], "formats": ["xlsx", "csv", "docx", "pdf"],
     "doc": "版式报告：封面 / 机房环境 / 内外网设备列表 / 评估项 / 现场巡检表 / "
            "逐条 display 命令回显截图 / 数据分析 / 维护建议"},
    {"key": "security", "name": "安全设备健康性检查报告",
     "sheets": ["安全设备信息", "检查项", "性能与告警"], "formats": ["xlsx", "csv", "docx", "pdf"],
     "doc": "版式报告：封面 / 机房环境 / 安全设备列表 / 安全评估项 / 现场巡检表 / "
            "逐条命令回显截图 / 数据分析 / 维护建议"},
    {"key": "alerts", "name": "告警与异常处置报告",
     "sheets": ["告警清单", "聚合告警", "收敛统计", "按设备汇总"], "formats": ["xlsx", "csv"]},
    {"key": "backup", "name": "配置备份完整性报告",
     "sheets": ["备份清单", "覆盖率汇总"], "formats": ["xlsx", "csv"]},
]


def meta() -> dict:
    values = settings()
    return {
        "site_name": values.get("site_name"),
        "org_name": values.get("org_name"),
        "health_rule": "健康度 = 100 − 巡检异常扣分 − CPU/内存阈值扣分（80%/90%）"
                       " − 接口错包扣分 − 离线扣分",
        "kind_rule": "设备类型由「型号 / 系统版本 / 厂商 / 角色」推断，可在台账页人工纠正",
        "data_flow": "设备（SSH 只读） → 本平台自带采集 → 本地 SQLite → "
                     "页面 / Excel / Word / PDF",
        "sources": [{"key": "local", "label": "本平台自带采集"}],
        "periods": [{"key": "1", "label": "近 1 天"}, {"key": "7", "label": "近 7 天"},
                    {"key": "30", "label": "近 30 天"},
                    {"key": "90", "label": "近 90 天"}],
    }

# ------------------------------------------------------------------ 全局搜索
def _device_blob(dev: dict) -> str:
    ledger = dev.get("ledger") or {}
    return " ".join([
        dev.get("name") or "", dev.get("ip") or "", dev.get("model") or "",
        dev.get("serial") or "", dev.get("vendor_display") or "",
        dev.get("group") or "", dev.get("region") or "", dev.get("type_label") or "",
        ledger.get("asset_no") or "", ledger.get("owner") or "",
        ledger.get("usage") or "", ledger.get("location") or "",
        ledger.get("note") or "",
    ]).lower()


def search(keyword: str, limit: int = 8) -> dict:
    """顶栏搜索：一次把设备台账 / 告警 / 备份 里命中的都列出来。

    返回分组结果，前端点哪条就跳到对应页面（设备→健康页、告警→报告中心、备份→备份页）。
    """
    kw = (keyword or "").strip().lower()
    result = {"keyword": keyword, "limit": limit, "devices": [], "alerts": [],
              "inspections": [], "backups": [], "reports": [], "logs": [],
              "total": 0, "source": "", "source_info": {}}
    if not kw:
        return result

    devices, source, info = devices_view()
    result["source"], result["source_info"] = source, info
    for dev in devices:
        if kw in _device_blob(dev):
            result["devices"].append({
                "id": dev["id"], "name": dev["name"], "ip": dev["ip"],
                "type_label": dev["type_label"], "model": dev["model"],
                "group_kind": dev["group_kind"],
                "health_label": dev["health_label"], "health_tone": dev["health_tone"],
                "owner": (dev.get("ledger") or {}).get("owner") or "",
                "asset_no": (dev.get("ledger") or {}).get("asset_no") or "",
            })

    alerts, _, _ = fetch("alerts", hours=24 * 180)
    for item in alerts:
        blob = " ".join([str(item.get("content") or ""), str(item.get("device") or ""),
                         str(item.get("device_ip") or ""), str(item.get("rule") or ""),
                         str(item.get("source_display") or "")]).lower()
        if kw in blob:
            key, label = nz.severity_view(item.get("severity"))
            result["alerts"].append({
                "id": item.get("id"),
                "title": item.get("content") or item.get("rule") or "告警",
                "device": item.get("device") or item.get("device_ip") or "",
                "device_ip": item.get("device_ip") or "",
                "severity": key, "severity_label": label,
                "status": item.get("status_display") or item.get("status") or "",
                "time": nz.fmt_time(item.get("triggered_at")),
            })

    backups = _normalize_backups({"files": fetch("backups")[0]})
    for item in backups:
        if kw in (item["name"] + " " + item["device_ip"]).lower():
            result["backups"].append({
                "name": item["name"], "device_ip": item["device_ip"],
                "size_text": _human_size(item["size"]),
                "time": nz.fmt_time(item["mtime"]),
            })

    for item in inspection_rows(hours=24 * 365, limit=2000).get("rows") or []:
        blob = " ".join(str(item.get(k) or "") for k in
                         ("device", "device_ip", "type", "issues", "owner", "asset_no", "location")).lower()
        if kw in blob:
            result["inspections"].append(item)

    for item in report_archive().get("exports") or []:
        blob = " ".join(str(item.get(k) or "") for k in
                         ("filename", "kind", "operator", "created_at")).lower()
        if kw in blob:
            result["reports"].append(item)

    for item in get_store().collect_logs(limit=500, with_raw=False):
        blob = " ".join(str(item.get(k) or "") for k in
                         ("device_name", "device_ip", "summary", "reason")).lower()
        if kw in blob:
            result["logs"].append(item)

    for key in ("devices", "alerts", "inspections", "backups", "reports", "logs"):
        result[key] = result[key][:limit]
        result["total"] += len(result[key])
    return result


# ------------------------------------------------------------------ 审计 / 账号（本平台）
def audit_rows(hours: int = 24 * 7, username: str = "", action: str = "",
               keyword: str = "", limit: int = 200) -> dict:
    """操作审计：读本平台自己的 auth_events（登录、账号、台账写入、远程登录…）。

    不再依赖任何外部平台的审计接口；事件由 auth.log_event 在写操作时记下。
    """
    from . import auth
    cache_key = "audit:%s:%s:%s:%s:%s" % (hours, username, action, keyword, limit)
    cached = cache_get(cache_key)
    if cached:
        return cached

    act = "" if (action or "").lower() in ("", "all") else action
    payload = auth.events(limit=limit, username=username, action=act, hours=hours)
    rows = payload.get("events") or []
    kw = (keyword or "").strip().lower()
    if kw:
        rows = [row for row in rows
                if kw in " ".join(str(row.get(k) or "") for k in
                                  ("username", "actor", "action_label", "detail", "ip")).lower()]
    action_labels = dict(payload.get("action_labels") or {})
    by_action: dict = {}
    by_user: dict = {}
    out = []
    for row in rows:
        event = row.get("action") or "other"
        by_action[event] = by_action.get(event, 0) + 1
        actor = row.get("actor") or row.get("username") or "系统"
        target = row.get("username") or ""
        bucket = by_user.setdefault(actor, {"username": actor, "count": 0,
                                            "last": "", "actions": {}})
        bucket["count"] += 1
        bucket["actions"][event] = bucket["actions"].get(event, 0) + 1
        stamp = row.get("created_at") or ""
        if stamp > bucket["last"]:
            bucket["last"] = stamp
        out.append({
            "id": row.get("id"), "username": actor, "actor": actor, "target": target,
            "action": event, "action_label": row.get("action_label") or event,
            "object_type": row.get("target_type") or "平台",
            "object_name": target or actor,
            "result": row.get("result") or "success",
            "detail": row.get("detail") or "", "ip": row.get("ip") or "",
            "time": nz.fmt_time(stamp), "created_at": stamp,
        })
    users = sorted(by_user.values(), key=lambda u: u["count"], reverse=True)
    for user in users:
        user["last_text"] = nz.fmt_time(user["last"])
        user["actions_text"] = "、".join(
            "%s %d" % (action_labels.get(k, k), v)
            for k, v in sorted(user["actions"].items(), key=lambda kv: -kv[1]))
    result = {"available": True, "error": "", "forbidden": False,
              "rows": out, "total": len(out),
              "by_action": by_action, "by_user": users,
              "action_labels": action_labels}
    cache_put(cache_key, result)
    return result


def users_overview(hours: int = 24 * 30, username: str = "", action: str = "",
                   keyword: str = "", limit: int = 200) -> dict:
    """账号总览：本平台自己的账号清单 + 本地操作审计。"""
    from . import auth
    accounts = auth.list_users()
    audit = audit_rows(hours=hours, username=username, action=action,
                       keyword=keyword, limit=limit)
    return {
        "accounts": accounts,
        "counts": {
            "total": len(accounts),
            "enabled": len([u for u in accounts if u.get("enabled")]),
            "admins": len([u for u in accounts if u.get("is_admin")]),
        },
        "audit": {
            "available": audit.get("available", False),
            "error": audit.get("error", ""),
            "rows": audit.get("rows") or [],
            "total": audit.get("total", 0),
            "by_action": audit.get("by_action") or {},
            "action_labels": audit.get("action_labels") or {},
            "filter": {"username": username, "action": action,
                       "keyword": keyword, "hours": hours},
        },
        "audit_available": audit.get("available", False),
        "audit_error": audit.get("error", ""),
        "period_hours": hours,
        "note": "账号与角色由本平台「用户与权限」维护；下面的审计是平台自己的操作留痕"
                "（登录、账号变更、台账写入、远程登录等），不依赖任何外部系统。",
    }


def templates_meta(use_cache: bool = True) -> dict:
    """报告与模板页的数据：本平台真实的报表模板 + 本地采集的数据来源。

    工作表清单要真跑一遍报表构造器才拿得到（9 套报表），比较费时，所以结果缓存一份：
    刷新页面不会每次都重算。
    """
    cached = cache_get("templates_meta") if use_cache else None
    if cached:
        return cached
    from . import report as report_module
    templates = []
    for key, builder in report_module.BUILDERS.items():
        label, workbook, _ = builder({"hours": 24 * 30, "days": 7, "device": ""})
        templates.append({
            "key": key, "name": label,
            "sheets": [ws.title for ws in workbook.worksheets],
        })
    result = {
        "templates": templates,
        "formats": ["xlsx", "csv", "docx", "pdf"],
        "sources": [
            {"object": "设备台账", "content": "设备名称 / IP / 厂商 / 型号 / 序列号 / 版本 / 角色 / 分组 / 地区",
             "method": "本平台台账维护 / CSV 导入 / 采集回填", "cycle": "按需", "source": "本地台账"},
            {"object": "交换机巡检", "content": "CPU / 内存 / STP 状态与端口 / 接口错包 / 巡检结论",
             "method": "SSH：display version / cpu-usage / memory-usage / interface / stp brief / alarm",
             "cycle": "采集周期（默认 60 分钟，可手动触发）", "source": "本平台自带采集"},
            {"object": "服务器巡检", "content": "主机名 / 型号 / 系统版本 / 运行时长 / CPU / 内存 / 磁盘 / 温度 / 服务 / 日志",
             "method": "SSH：uname / top / free / df / systemctl / journalctl；Windows 走 Get-CimInstance 等",
             "cycle": "采集周期（默认 60 分钟，可手动触发）", "source": "本平台自带采集"},
            {"object": "配置备份", "content": "交换机每台一个设备名.cfg；服务器按设备名目录保留原始备份文件；统一 ZIP 下载",
             "method": "实时 SSH：交换机 dis cu；服务器 SFTP 读取采集设置中的备份目录",
             "cycle": "按需（浏览器下载）", "source": "内存生成，不落盘"},
            {"object": "告警事件", "content": "级别 / 状态 / 设备 / 指标 / 取值 / 内容",
             "method": "本平台阈值判定 + 与上一轮比较的变化检测", "cycle": "每次采集后", "source": "本平台告警中心"},
            {"object": "操作审计", "content": "操作人 / 动作 / 对象 / 详情 / 来源 IP / 时间",
             "method": "本平台写操作留痕", "cycle": "写操作即记录", "source": "本平台审计"},
        ],
        "notes": [
            "报表由本平台现算生成：表格中的数据全部来自本地采集库，导出即归档。",
            "Word / PDF 版式报告（服务器、交换机健康性检查报告）由本平台直接排版生成："
            "封面、机房环境、设备列表、评估项、现场巡检表、逐条命令回显截图、数据分析与"
            "维护建议；命令回显取自本平台自带采集留档的原始回显，未留档时如实注明。",
            "采集对象与周期在「远程运维 → 采集任务 → 采集设置」里配置，默认开启定时采集。",
        ],
    }
    if use_cache:
        cache_put("templates_meta", result)
    return result


















