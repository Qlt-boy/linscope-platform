# -*- coding: utf-8 -*-
"""采集执行器：登录华为交换机 → 跑只读命令 → 解析 → 写库（台账/巡检/监控/告警/备份）。

* **凭据复用**远程登录模块的加密凭据库（`app.remote.credentials_list/credential_get`），
  一套账号既用于控制台登录，也用于采集，不用填两遍；
* **并发**：线程池（默认 5 台并行），单台超时可控，失败不影响其它设备；
* **写库**：设备信息回填（型号/序列号/版本）、巡检记录、SNMP 式监控记录、本地判定告警、
  可选配置备份；每次任务写 `collect_runs`，每台设备写 `collect_logs`（含执行过的命令与摘要），
  排查问题不用再登设备；
* **不编数**：解析不到的字段留空，页面照实显示「未采集」。
"""
from __future__ import annotations

import concurrent.futures
import io
import os
import re
import time
from datetime import datetime, timedelta

import paramiko

from .. import config
from .. import normalize as nz
from .. import remote as remote_login
from ..store import get_store, next_row_id
from . import huawei, server

try:                                            # paramiko 缺失时给出可读错误
    import paramiko as _paramiko
except Exception:                               # pragma: no cover
    _paramiko = None

import threading

_RUN_LOCK = threading.Lock()

PROMPT_RE = re.compile(r"[<\[][A-Za-z0-9_.\-]+[>\]]\s*$")
CONFIG_DIR = os.path.join(str(config.DATA_DIR), "config-backups")

DEFAULT_SETTINGS = {
    "enabled": "1",                                  # 定时采集开关
    "interval_minutes": "60",                        # 定时采集周期
    "concurrency": "5",                              # 并发台数
    "timeout": "25",                                 # 单台超时（秒）
    "with_config": "0",                              # 是否顺带抓配置备份
    "alert_cooldown_hours": "24",                     # 同类告警去重窗口
    # 变化检测（跟该设备上一次采集比，只有"变化"才报，避免天天重复）
    "alert_on_change": "1",                          # 开关
    "cpu_delta": "30",                               # CPU 上升多少个百分点算突增
    "mem_delta": "25",                               # 内存上升多少个百分点算突增
    "err_delta": "100",                              # 错误包增量多少算快速增长
    "high_pct": "80",                                # 高位阈值
    "high_streak": "3",                              # 连续几次高位才提醒
    # 服务器采集（SSH，只读）：备份目录用于「备份检查」回显，留空用默认值
    "server_backup_path_linux": "",                  # 默认 /var/backups
    "server_backup_path_windows": "",                # 默认 C:\Backup
}


class CollectError(Exception):
    pass


#: 自带采集支持：华为 VRP 交换机 + Linux / Windows(OpenSSH) 服务器
def profile_of(device: dict) -> str:
    """判断用哪套采集器：server（Linux/Windows）/ vrp（华为交换机）。"""
    device = device or {}
    try:
        from .. import normalize as _nz
        kind = _nz.infer_kind(device, device.get("kind") or "")
        if kind == "server":
            return "server"
    except Exception:                                   # noqa: BLE001
        pass
    if str(device.get("os_type") or "").strip().lower() in ("linux", "windows"):
        return "server"
    return "vrp"


def is_supported(device: dict) -> bool:
    if profile_of(device) == "server":
        return True
    vendor = str((device or {}).get("vendor") or (device or {}).get("vendor_display") or "")
    vendor = vendor.strip().lower()
    if not vendor:
        return True                     # 没写厂商的按华为试一把，失败原因会写进采集日志
    return ("huawei" in vendor) or ("华为" in vendor)


def _scheduler_state() -> dict:
    """取定时器状态（惰性导入，避免 runner ↔ scheduler 循环依赖）。"""
    try:
        from . import scheduler
        return scheduler.state()
    except Exception:
        return {}


# ------------------------------------------------------------------ 设置
def settings() -> dict:
    store = get_store()
    values = dict(DEFAULT_SETTINGS)
    try:
        with store.connect() as conn:
            for row in conn.execute("SELECT key, value FROM settings"
                                    " WHERE key LIKE 'collect.%'"):
                values[row["key"].split(".", 1)[1]] = row["value"]
    except Exception:
        pass
    return values


def save_settings(payload: dict) -> dict:
    store = get_store()
    current = settings()
    for key, value in (payload or {}).items():
        if key not in DEFAULT_SETTINGS or value is None:
            continue
        current[key] = str(value)
    store.save_settings({"collect.%s" % k: v for k, v in current.items()})
    return settings()


# ------------------------------------------------------------------ SSH 会话
class VrpSession:
    """华为 VRP 的交互式会话：读回显读到提示符为止（比 exec 通道稳）。"""

    def __init__(self, client, timeout: float = 25.0):
        self.client = client
        self.timeout = timeout
        self.channel = client.invoke_shell(term="vt100", width=200, height=1000)
        self.channel.settimeout(0.3)
        self.buffer = ""
        self._read_until_prompt(initial=True)

    def _read_until_prompt(self, initial: bool = False, idle_limit: float = 3.0) -> str:
        deadline = time.time() + self.timeout
        last_data = time.time()
        text = ""
        while time.time() < deadline:
            try:
                data = self.channel.recv(65536)
            except Exception:
                data = b""
            if data:
                chunk = data.decode("utf-8", "replace")
                text += chunk
                last_data = time.time()
                if PROMPT_RE.search(text.rstrip()):
                    break
                continue
            if text and (time.time() - last_data) > idle_limit:
                break
            if initial and not text and (time.time() - last_data) > idle_limit:
                break
        self.buffer += text
        return text

    def run(self, command: str) -> str:
        """执行一条命令，返回去掉回显与提示符的输出。"""
        try:
            self.channel.send(command + "\n")
        except Exception as exc:
            raise CollectError("发送命令失败：%s" % exc)
        raw = self._read_until_prompt()
        lines = raw.splitlines()
        output = []
        for index, line in enumerate(lines):
            if index == 0 and command.split()[0] in line and command[:20] in line:
                continue                                   # 去掉回显的命令本身
            if PROMPT_RE.search(line) and index >= len(lines) - 2:
                continue                                   # 去掉结尾提示符
            if "---- More ----" in line:
                continue
            output.append(line)
        return "\n".join(output).strip()

    def close(self) -> None:
        for closer in (self.channel, self.client):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass


def _connect(ip: str, timeout: float):
    """采集与远程控制台共用同一套凭据和 SSH 主机指纹校验。"""
    try:
        client, _cred = remote_login._connect(ip, timeout)
        return client
    except remote_login.RemoteError as exc:
        message = str(exc)
        if "认证失败" in message:
            raise CollectError("认证失败：账号或口令不对")
        raise CollectError(message)


def collect_device(ip: str, name: str = "", timeout: float = 25.0,
                   with_config: bool = False, profile: str = "vrp",
                   device: dict | None = None) -> dict:
    """采集一台设备（华为交换机 / Linux / Windows），返回解析后的记录（不写库）。"""
    if _paramiko is None:
        raise CollectError("缺少 paramiko 依赖")
    started = time.time()
    client = _connect(ip, timeout)

    if profile == "server":
        try:
            conf = settings()
            records = server.collect_from_client(
                client, device or {"name": name, "ip": ip}, timeout=timeout,
                os_type=str((device or {}).get("os_type") or ""),
                backup_paths={"linux": conf.get("server_backup_path_linux") or "",
                              "windows": conf.get("server_backup_path_windows") or ""})
            return records
        except CollectError:
            raise
        except Exception as exc:                        # noqa: BLE001
            raise CollectError("服务器采集失败：%s: %s" % (type(exc).__name__, exc))
        finally:
            try:
                client.close()
            except Exception:                           # noqa: BLE001
                pass

    session = None
    commands_done = []
    try:
        session = VrpSession(client, timeout)
        for command in huawei.PREPARE_COMMANDS:            # 关分屏
            session.run(command)
            commands_done.append(command)
        raw = {}
        for key, command in huawei.COMMANDS:
            try:
                raw[key] = session.run(command)
                commands_done.append(command)
            except CollectError:
                raw[key] = ""
        if with_config:
            try:
                raw["config"] = session.run(huawei.CONFIG_COMMAND)
                commands_done.append(huawei.CONFIG_COMMAND)
            except CollectError:
                raw["config"] = ""
    finally:
        if session is not None:
            session.close()
        else:
            try:
                client.close()
            except Exception:
                pass
    records = huawei.build_records(raw, {"name": name, "ip": ip})
    records["raw"] = raw
    records["commands"] = commands_done
    records["duration_ms"] = int((time.time() - started) * 1000)
    return records


#: 回显摘要在日志里最多留这么多字符（够排错，又不至于把库撑大）
RAW_KEEP = {"version": 700, "cpu": 500, "memory": 400, "interfaces": 1200,
            "stp": 700, "lldp": 800, "alarm": 700, "serial": 300, "config": 1500}


def raw_excerpt(raw: dict, kind: str = "vrp") -> str:
    """把关键命令的原始回显裁剪成一份摘要，随采集日志一起留档。"""
    if kind == "server":
        return server.raw_excerpt(raw or {})
    parts = []
    for key, limit in RAW_KEEP.items():
        text = (raw or {}).get(key) or ""
        if not text.strip():
            continue
        body = text.strip()
        if len(body) > limit:
            body = body[:limit] + "\n…（截断，完整回显未留存）"
        parts.append("──── %s ────\n%s" % (key, body))
    return "\n".join(parts)[:8000]


# ------------------------------------------------------------------ 变化检测
def _int_setting(conf: dict, key: str, default: int) -> int:
    try:
        return int(float(conf.get(key) or default))
    except (TypeError, ValueError):
        return default


def _enabled(conf: dict, key: str, default: bool = True) -> bool:
    raw = conf.get(key)
    if raw is None:
        return default
    return str(raw).lower() in ("1", "true", "on", "yes")


def detect_changes(store, ip: str, device: dict, inspection: dict,
                   records: dict, conf: dict) -> list:
    """跟该设备**上一次采集**比，只把"变化"报成告警。

    对比项：CPU / 内存突增、端口由 up 变 down（及恢复）、错包快速增长、
    STP 由启用变禁用、设备重启（uptime 变小）、CPU/内存连续多次高位。
    """
    if not _enabled(conf, "alert_on_change", True):
        return []
    history = store.recent_inspections(ip, limit=max(3, _int_setting(conf, "high_streak", 3)))
    prev = history[0] if history else {}
    alerts = []
    name = device.get("name") or ip

    cpu_now = inspection.get("device_cpu")
    cpu_prev = (prev or {}).get("cpu") if prev else None
    mem_now = inspection.get("device_memory")
    mem_prev = (prev or {}).get("memory") if prev else None
    if prev and cpu_now is not None and cpu_prev is not None:
        delta = float(cpu_now) - float(cpu_prev)
        if delta >= _int_setting(conf, "cpu_delta", 30):
            alerts.append({"source": "monitor", "severity": "4", "metric": "cpu_spike",
                           "dedupe_key": "cpu_spike",
                           "content": "CPU 使用率突增：%.0f%% → %.0f%%（较上次 +%.0f 个百分点）"
                                      % (cpu_prev, cpu_now, delta),
                           "value": cpu_now})
    if prev and mem_now is not None and mem_prev is not None:
        delta = float(mem_now) - float(mem_prev)
        if delta >= _int_setting(conf, "mem_delta", 25):
            alerts.append({"source": "monitor", "severity": "4", "metric": "memory_spike",
                           "dedupe_key": "memory_spike",
                           "content": "内存使用率突增：%.0f%% → %.0f%%（较上次 +%.0f 个百分点）"
                                      % (mem_prev, mem_now, delta),
                           "value": mem_now})

    # 端口状态变化（只看变化，不重复报"一直是 down"）
    def down_set(rec):
        """上一轮 down 的端口名集合；上一轮没存端口明细时返回 None（不做端口变化判定）。"""
        ports = (rec or {}).get("ports")
        if isinstance(ports, list) and ports:
            return {p.get("name") for p in ports if p.get("name") and not p.get("up")}
        raw = (rec or {}).get("error_ports")
        if isinstance(raw, (list, tuple, set)):
            return {str(x) for x in raw if x}
        return None                                 # 老记录只有统计值，拿不到端口名

    prev_ports = down_set(prev) if prev else None
    now_ports = {p["name"] for p in (records.get("ports") or []) if not p["up"]}
    for port in (sorted(now_ports - prev_ports) if prev_ports is not None else []):
        desc = next((p.get("description") or "" for p in (records.get("ports") or [])
                     if p["name"] == port), "")
        alerts.append({"source": "monitor", "severity": "2", "metric": "port_down_new",
                       "dedupe_key": "port_down_new:%s" % port,
                       "content": "端口新变为 down：%s%s（上次采集时还是 up）"
                                  % (port, ("（" + desc + "）") if desc else ""),
                       "value": None})
    for port in (sorted(prev_ports - now_ports) if prev_ports is not None else []):
        if not port:
            continue
        alerts.append({"source": "monitor", "severity": "6", "metric": "port_up",
                       "dedupe_key": "port_up:%s" % port,
                       "content": "端口已恢复：%s（上次采集时是 down）" % port, "value": None})

    # 错包增长
    prev_err = (prev or {}).get("error_total")
    now_err = inspection.get("error_total")
    if prev_err is not None and now_err is not None:
        grow = int(now_err) - int(prev_err)
        if grow >= _int_setting(conf, "err_delta", 100):
            alerts.append({"source": "monitor", "severity": "4", "metric": "if_errors_growth",
                           "dedupe_key": "if_errors_growth",
                           "content": "接口错误包快速增长：较上次 +%d 个（累计 %d）" % (grow, now_err),
                           "value": grow})

    # STP 由启用变禁用
    prev_stp = str((prev or {}).get("stp_state") or "").lower()
    now_stp = str(inspection.get("stp_state") or "").lower()
    if prev_stp == "enabled" and now_stp == "disabled":
        alerts.append({"source": "monitor", "severity": "2", "metric": "stp_disabled",
                       "dedupe_key": "stp_disabled",
                       "content": "STP 由「启用」变为「禁用」（存在环路风险）", "value": None})

    # 设备重启（uptime 变小）；老记录里没存秒数时回落成现场解析文本
    now_up = records.get("uptime_seconds")
    if now_up is None:
        now_up = huawei.uptime_to_seconds(records.get("uptime") or "")
    prev_up = (prev or {}).get("uptime_seconds") if prev else None
    if prev_up is None and prev:
        prev_up = huawei.uptime_to_seconds(prev.get("uptime_text") or "")
    if prev_up is not None and now_up is not None and now_up < prev_up - 300:
        alerts.append({"source": "monitor", "severity": "4", "metric": "device_reboot",
                       "dedupe_key": "device_reboot",
                       "content": "设备疑似重启：运行时长由 %s 变为 %s"
                                  % ((prev or {}).get("uptime_text") or "—",
                                     records.get("uptime_text") or "—"),
                       "value": None})

    # 连续高位（不是"变化"，但值得提醒）
    streak = _int_setting(conf, "high_streak", 3)
    high_pct = _int_setting(conf, "high_pct", 80)
    if streak >= 2 and history:
        recent = [cpu_now] + [(h or {}).get("cpu") for h in history[:streak - 1]]
        values = [float(v) for v in recent if v is not None]
        if len(values) >= streak and all(v >= high_pct for v in values):
            alerts.append({"source": "monitor", "severity": "4", "metric": "cpu_sustained",
                           "dedupe_key": "cpu_sustained",
                           "content": "CPU 连续 %d 次采集 ≥ %d%%（最近 %.0f%%）"
                                      % (len(values), high_pct, values[0]), "value": values[0]})
        recent_mem = [mem_now] + [(h or {}).get("memory") for h in history[:streak - 1]]
        mem_values = [float(v) for v in recent_mem if v is not None]
        if len(mem_values) >= streak and all(v >= high_pct for v in mem_values):
            alerts.append({"source": "monitor", "severity": "4", "metric": "memory_sustained",
                           "dedupe_key": "memory_sustained",
                           "content": "内存连续 %d 次采集 ≥ %d%%（最近 %.0f%%）"
                                      % (len(mem_values), high_pct, mem_values[0]),
                           "value": mem_values[0]})
    return alerts


# ------------------------------------------------------------------ 写库
def _write_server_records(ip: str, device: dict, records: dict, run_id: int) -> str:
    """服务器采集结果写库：台账 / 巡检 / 监控 / 指标 / 告警。

    与交换机共用同一套表：巡检记录里 CPU/内存照常写，STP / 错包留空；
    磁盘、温度、未运行服务数写进 metrics（服务器健康页与报告都读这张表）。
    """
    store = get_store()
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    info = records.get("device") or {}
    is_win = records.get("os_type") == "windows"

    merged = dict(device)
    ledger_name = str(device.get("name") or "").strip()
    collected_name = str(info.get("name") or "").strip()
    merged.update({
        "ip": ip,
        # 台账里已有人工命名的保留；只有没名字或名字就是 IP 时才用采集到的主机名回填
        "name": (ledger_name if ledger_name and ledger_name != ip
                 else (collected_name or ledger_name or ip)),
        "hostname": collected_name,
        # 显式标成服务器：设备台账按类型分区时不会再被推断成「其他设备」
        "kind": "server",
        "os_type": records.get("os_type"),
        "vendor": device.get("vendor") or ("windows" if is_win else "linux"),
        "vendor_display": (device.get("vendor_display") or info.get("vendor_display")
                           or ("Windows Server" if is_win else "Linux 服务器")),
        "model": info.get("model") or device.get("model") or "",
        "serial": info.get("serial") or device.get("serial") or "",
        "version": info.get("version") or device.get("version") or "",
        "online": True,
        "pending_collection": False,
        "last_online_at": stamp,
        "updated_at": stamp,
        "source": "local",
    })
    store.device_upsert(merged)

    inspection = dict(records.get("inspection") or {})
    inspection.update({
        "device_id": merged.get("id"), "device": merged["name"], "device_ip": ip,
        "run_id": "COLLECT-%d" % run_id, "inspected_at": stamp, "error": "",
        "ports": [], "uptime_text": records.get("uptime") or "",
        "uptime_seconds": records.get("uptime_seconds"),
    })
    change_alerts = detect_changes(store, ip, merged, inspection, records, settings())

    store.save_inspections([{
        "id": next_row_id(),
        "run_id": inspection["run_id"], "device_id": inspection["device_id"],
        "device": inspection["device"], "device_ip": ip,
        "cpu": inspection.get("device_cpu"), "memory": inspection.get("device_memory"),
        "stp_state": "", "stp_mode": "", "stp_forward": None, "stp_blocked": None,
        "error_ports": 0, "error_total": 0,
        "healthy": bool(inspection.get("healthy")),
        "issues": inspection.get("issues") or "", "error": "",
        "inspected_at": stamp, "ports": [],
        "uptime_text": inspection.get("uptime_text") or "",
        "uptime_seconds": inspection.get("uptime_seconds"),
    }])

    monitor = dict(records.get("monitor") or {})
    store.save_monitors([{
        "id": next_row_id(), "device_id": merged.get("id"),
        "device": merged["name"], "device_ip": ip,
        "sysname": monitor.get("sysname") or merged["name"],
        "serial": monitor.get("serial") or "", "version": monitor.get("version") or "",
        "cpu": monitor.get("cpu"), "memory": monitor.get("memory"),
        "ok": True, "error": "", "collected_at": stamp,
    }])

    rows = []
    for item in records.get("metrics") or []:
        if item.get("value") is None:
            continue
        rows.append({"id": next_row_id(), "device_id": merged.get("id"),
                     "device": merged["name"], "device_ip": ip,
                     "metric": item.get("metric") or "metric",
                     "label": item.get("label") or item.get("metric") or "",
                     "value": item.get("value"), "unit": item.get("unit") or "",
                     "source": "collect", "collected_at": stamp})
    if rows:
        store.save_metrics(rows)

    written = _write_alerts(store, ip, merged,
                            (records.get("alerts") or []) + change_alerts, run_id)

    def pct(value):
        return "—" if value is None else "%.0f%%" % value

    failed = next((m.get("value") for m in records.get("metrics") or []
                   if m.get("metric") == "failed_services"), None)
    summary = ("CPU %s · 内存 %s · 磁盘 %s · 未运行服务 %s · 告警 %d"
               % (pct(inspection.get("device_cpu")), pct(inspection.get("device_memory")),
                  pct(next((m.get("value") for m in records.get("metrics") or []
                            if m.get("metric") == "disk"), None)),
                  "—" if failed is None else "%d 个" % failed, len(written)))
    if change_alerts:
        fresh = [_alert_key(a) for a in change_alerts if _alert_key(a) in written]
        if fresh:
            summary += " · 变化提醒 %d 条" % len(fresh)
    return summary


def _write_records(ip: str, device: dict, records: dict, run_id: int,
                   with_config: bool) -> str:
    """把采集结果写进本平台库（台账/巡检/监控/告警/备份），返回一句摘要。"""
    if records.get("kind") == "server":
        return _write_server_records(ip, device, records, run_id)
    store = get_store()
    now = datetime.now()
    info = records["device"]

    merged = dict(device)
    ledger_name = str(device.get("name") or "").strip()
    collected_name = str(info.get("name") or info.get("hostname") or "").strip()
    merged.update({
        "ip": ip,
        "name": (ledger_name if ledger_name and ledger_name != ip
                 else (collected_name or ledger_name or ip)),
        "hostname": collected_name,
        "vendor": "huawei",
        "vendor_display": "华为",
        "model": info.get("model") or device.get("model") or "",
        "serial": info.get("serial") or device.get("serial") or "",
        "version": info.get("version") or device.get("version") or "",
        "online": True,
        "pending_collection": False,
        "last_online_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "local",
    })
    store.device_upsert(merged)

    inspection = dict(records["inspection"])
    inspection.update({"device_id": merged.get("id"), "device": merged["name"],
                       "device_ip": ip, "run_id": "COLLECT-%d" % run_id,
                       "inspected_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                       "error": "",
                       # 变化检测要用到的上下文（端口明细 / 运行时长）
                       "ports": [{"name": p["name"], "up": p["up"],
                                  "description": p.get("description") or ""}
                                 for p in (records.get("ports") or [])],
                       "uptime_text": records.get("uptime") or "",
                       "uptime_seconds": records.get("uptime_seconds")})
    # 先跟**上一轮**比出变化，再写这一轮的巡检记录：写库之后 recent_inspections
    # 的第一条就是本轮自己，会变成"自己跟自己比"（永远检测不到任何变化）
    change_alerts = detect_changes(store, ip, merged, inspection, records, settings())

    store.save_inspections([{
        "id": next_row_id(),
        "run_id": inspection["run_id"], "device_id": inspection["device_id"],
        "device": inspection["device"], "device_ip": ip,
        "cpu": inspection["device_cpu"], "memory": inspection["device_memory"],
        "stp_state": inspection["stp_state"], "stp_mode": inspection["stp_mode"],
        "stp_forward": inspection["stp_forward"], "stp_blocked": inspection["stp_blocked"],
        "error_ports": inspection["error_ports"], "error_total": inspection["error_total"],
        "healthy": inspection["healthy"], "issues": inspection["issues"],
        "error": "", "inspected_at": inspection["inspected_at"],
        # 端口状态快照 + 运行时长：payload 里带上，下一轮才能判断"端口新变 down /
        # 已恢复 / 设备重启"，否则每轮都会把"一直是 down"重复报成"新变 down"
        "ports": inspection["ports"], "uptime_text": inspection["uptime_text"],
        "uptime_seconds": inspection["uptime_seconds"],
        "lldp": records.get("lldp") or [],
    }])

    monitor = dict(records["monitor"])
    monitor.update({"device_id": merged.get("id"), "device": merged["name"],
                    "device_ip": ip, "collected_at": now.strftime("%Y-%m-%d %H:%M:%S")})
    store.save_monitors([{
        "id": next_row_id(),
        "device_id": monitor["device_id"], "device": monitor["device"],
        "device_ip": ip, "sysname": monitor["sysname"], "serial": monitor["serial"],
        "version": monitor["version"], "cpu": monitor["cpu"], "memory": monitor["memory"],
        "ok": True, "error": "", "collected_at": monitor["collected_at"],
    }])

    written = _write_alerts(store, ip, merged, records["alerts"] + change_alerts, run_id)
    added_alerts = len(written)
    # 只有真正写进告警表的"变化"才在摘要里点名（去重窗口内不重复报）
    from .. import normalize as nz
    fresh = [_alert_key(a) for a in change_alerts if _alert_key(a) in written]
    if fresh:
        labels = []
        for alert in change_alerts:
            label = nz.change_metric_label(alert.get("metric"))
            if label and _alert_key(alert) in written and label not in labels:
                labels.append(label)
        summary_more = " · 变化提醒 %d 条（%s）" % (len(fresh), "、".join(labels))
    else:
        summary_more = ""

    backup_note = ""
    if with_config and records["raw"].get("config"):
        BACKUP_DIR_ABS = CONFIG_DIR
        os.makedirs(BACKUP_DIR_ABS, exist_ok=True)
        stamp = now.strftime("%Y%m%d_%H%M%S")
        safe_ip = ip.replace(":", "_")
        name = "backup_%s_%s.cfg" % (safe_ip, stamp)
        path = os.path.join(BACKUP_DIR_ABS, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(records["raw"]["config"])
        store.save_backups([{"name": name, "device_ip": ip,
                             "size": os.path.getsize(path),
                             "mtime": now.strftime("%Y-%m-%d %H:%M:%S")}])
        backup_note = "，已备份配置"

    summary = ("CPU %s%% · 内存 %s%% · 端口 down %d · 错包口 %d · 告警 %d%s"
               % ("—" if monitor["cpu"] is None else "%.0f" % monitor["cpu"],
                  "—" if monitor["memory"] is None else "%.0f" % monitor["memory"],
                  len([p for p in records["ports"] if not p["up"]]),
                  int(inspection["error_ports"] or 0), added_alerts,
                  summary_more + backup_note))
    return summary


def _alert_key(alert: dict) -> str:
    """告警去重键：优先用告警自带的 dedupe_key（端口级/指标级），老格式回落成内容。"""
    return str(alert.get("dedupe_key") or alert.get("content")
               or alert.get("metric") or "")


def _write_alerts(store, ip: str, device: dict, alerts: list, run_id: int) -> set:
    """本地判定告警写库（去重窗口内同类不重复刷屏）。

    去重键用告警自带的 `dedupe_key`：

    * 端口级（`if_errors:Gi0/0/3`、`port_down_new:Gi0/0/2`）：同一个端口不会重复报，
      另一个端口 down 仍然单独报，错包计数每轮都在涨也不会刷屏；
    * 指标级（`cpu_spike`、`memory_sustained`、`device_reboot`…）：内容里带的是每次
      都不同的数值，按「设备 + 指标」在去重窗口内只留一条。

    返回**实际写入**的去重键集合（被去重挡掉的不算），页面/日志据此显示真实新增条数。
    """
    if not alerts:
        return set()
    cooldown = int(settings().get("alert_cooldown_hours") or 24)
    since = (datetime.now() - timedelta(hours=cooldown)).strftime("%Y-%m-%d %H:%M:%S")
    existing = set()
    for old in store.alerts(limit=500):
        if (old.get("triggered_at") or "") < since or old.get("device_ip") != ip:
            continue
        existing.add(_alert_key(old))

    rows = []
    for alert in alerts:
        key = _alert_key(alert)
        if key in existing:
            continue
        existing.add(key)
        rows.append({
            "id": next_row_id(),
            "source": alert["source"], "source_display": "本平台采集",
            "severity": alert["severity"], "status": "new",
            "status_display": "未处理", "device_ip": ip,
            "device": device.get("name") or ip, "rule": "本平台采集判定",
            "metric": alert["metric"], "value": alert.get("value"),
            "content": alert["content"], "dedupe_key": key,
            "triggered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    if rows:
        store.save_alerts(rows)
    return {r["dedupe_key"] for r in rows}


# ------------------------------------------------------------------ 批量任务
def run(ips: list | None = None, trigger: str = "manual", with_config: bool | None = None,
        operator: str = "admin") -> dict:
    """跑一轮采集（默认全部启用的设备）。"""
    store = get_store()
    if not _RUN_LOCK.acquire(blocking=False):
        raise CollectError("已有一轮采集在进行中，请稍后再试")
    try:
        return _run_locked(ips, trigger, with_config, operator)
    finally:
        _RUN_LOCK.release()


def _run_locked(ips, trigger, with_config, operator) -> dict:
    store = get_store()
    conf = settings()
    if with_config is None:
        with_config = str(conf.get("with_config")) in ("1", "true", "on", "yes")
    timeout = float(conf.get("timeout") or 25)
    concurrency = max(1, min(20, int(conf.get("concurrency") or 5)))

    devices = store.devices()
    if ips:
        wanted = {ip.strip() for ip in ips if ip.strip()}
        devices = [d for d in devices if d.get("ip") in wanted]
    devices = [d for d in devices if d.get("ip")]
    # 全量采集（定时任务 / 立即采集）只跑"已配凭据"的设备；没配凭据的直接跳过，
    # 不写失败日志（否则每小时都会刷一条“没有配置登录凭据”的失败记录）。
    try:
        credentialed = {c.get("ip") for c in remote_login.credentials_list()}
    except Exception:                                   # noqa: BLE001
        credentialed = set()
    no_cred = []
    if not ips:
        no_cred = [d for d in devices if d.get("ip") not in credentialed]
        devices = [d for d in devices if d.get("ip") in credentialed]
    unsupported = [d for d in devices if not is_supported(d)]
    devices = [d for d in devices if is_supported(d)]
    run_id = store.collect_run_start(trigger, operator)
    started = time.time()
    ok = failed = skipped = 0
    skipped_unsupported = skipped_no_cred = 0
    details = []
    for device in unsupported:                      # 非华为/非服务器设备：不采集，只记明细
        skipped += 1
        skipped_unsupported += 1
        details.append({
            "ip": device.get("ip"), "name": device.get("name") or "",
            "ok": None, "skipped": True,
            "error": "跳过：自带采集只支持华为 VRP 交换机与 Linux/Windows 服务器（当前：%s），"
                     "该设备可在「远程登录」里操作"
                     % (device.get("vendor_display") or device.get("vendor") or "未知厂商"),
        })
    for device in no_cred:                          # 未配凭据：跳过，不写失败日志
        skipped += 1
        skipped_no_cred += 1
        details.append({
            "ip": device.get("ip"), "name": device.get("name") or "",
            "ok": None, "skipped": True,
            "error": "跳过：未配置 SSH 凭据（到「设备清单 → 凭据」填写后即可采集）",
        })

    def mark(ip, online, error=""):
        """采集结果回写设备的"连接状态"：成功=在线并清错误；失败=离线并记录原因。"""
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values = {"online": bool(online), "last_checked_at": stamp,
                  "last_error": "" if online else str(error or "")[:200]}
        if online:
            values["last_online_at"] = stamp
        try:
            store.device_mark(ip, values)
        except Exception:                               # noqa: BLE001
            pass

    def one(device):
        ip = device.get("ip")
        try:
            records = collect_device(ip, device.get("name") or "", timeout, with_config,
                                     profile_of(device), device)
            summary = _write_records(ip, device, records, run_id, with_config)
            mark(ip, True)
            store.collect_log(run_id, ip, device.get("name") or "", True, "",
                              records["duration_ms"], " ; ".join(records["commands"]),
                              summary, raw_excerpt(records.get("raw") or {},
                                                   records.get("kind") or "vrp"))
            return {"ip": ip, "name": device.get("name") or "", "ok": True,
                    "summary": summary, "duration_ms": records["duration_ms"]}
        except CollectError as exc:
            mark(ip, False, str(exc))
            store.collect_log(run_id, ip, device.get("name") or "", False, str(exc), 0, "",
                              "")
            return {"ip": ip, "name": device.get("name") or "", "ok": False,
                    "error": str(exc)}
        except Exception as exc:                       # noqa: BLE001
            mark(ip, False, "%s: %s" % (type(exc).__name__, exc))
            store.collect_log(run_id, ip, device.get("name") or "", False,
                              "%s: %s" % (type(exc).__name__, exc), 0, "", "")
            return {"ip": ip, "name": device.get("name") or "", "ok": False,
                    "error": "%s: %s" % (type(exc).__name__, exc)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        for result in pool.map(one, devices):
            details.append(result)
            if result["ok"]:
                ok += 1
            else:
                failed += 1

    duration_ms = int((time.time() - started) * 1000)
    message = ("完成：成功 %d / 失败 %d / 共 %d 台" % (ok, failed, len(devices)))
    if skipped:
        reasons = []
        if skipped_unsupported:
            reasons.append("不支持采集 %d 台" % skipped_unsupported)
        if skipped_no_cred:
            reasons.append("未配凭据 %d 台" % skipped_no_cred)
        message += "，跳过 %d 台（%s）" % (skipped, "、".join(reasons))
    store.collect_run_finish(run_id, len(devices), ok, failed, skipped, duration_ms, message)
    from .. import service
    service.cache_clear()
    return {"run_id": run_id, "ok": ok, "failed": failed, "skipped": skipped,
            "total": len(devices) + skipped, "duration_ms": duration_ms,
            "message": message,
            "with_config": with_config, "trigger": trigger, "details": details[:200]}


def precheck(ips: list | None = None, timeout: float = 2.5) -> dict:
    """采集前连通性预检：只做 TCP 探测（不登录），先筛掉网络不通的。

    目的：批量采集时"连不上"往往占掉大半时间与失败日志，先探一遍端口能少很多噪声。
    """
    import socket

    store = get_store()
    devices = store.devices()
    if ips:
        wanted = {str(ip).strip() for ip in ips if str(ip).strip()}
        devices = [d for d in devices if d.get("ip") in wanted]
    devices = [d for d in devices if d.get("ip")]

    credentials = {c["ip"]: c for c in remote_login.credentials_list()}

    def probe(device):
        ip = device["ip"]
        cred = credentials.get(ip) or {}
        port = int(cred.get("port") or device.get("port") or 22)
        started = time.time()
        sock = socket.socket()
        sock.settimeout(timeout)
        try:
            sock.connect((ip, port))
            return {"ip": ip, "name": device.get("name") or ip, "port": port,
                    "reachable": True, "latency_ms": int((time.time() - started) * 1000),
                    "credential_ready": ip in credentials, "error": ""}
        except Exception as exc:
            return {"ip": ip, "name": device.get("name") or ip, "port": port,
                    "reachable": False,
                    "latency_ms": int((time.time() - started) * 1000),
                    "credential_ready": ip in credentials,
                    "error": "%s: %s" % (type(exc).__name__, exc)}
        finally:
            try:
                sock.close()
            except Exception:
                pass

    results = []
    if devices:
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, min(20, int(settings().get("concurrency") or 5) * 2))) as pool:
            results = list(pool.map(probe, devices))
    ok = [r for r in results if r["reachable"]]
    return {"total": len(results), "reachable": len(ok),
            "unreachable": len(results) - len(ok), "timeout": timeout,
            "results": results,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


def logs_csv(ip: str = "", only_failed: bool = False, run_id: int = 0,
             limit: int = 1000, with_raw: bool = False) -> str:
    """采集日志导出 CSV（带 UTF-8 BOM，Excel 双击不乱码）。"""
    import csv
    import io as _io

    store = get_store()
    rows = store.collect_logs(ip=ip, limit=limit, run_id=run_id,
                              only_failed=only_failed, with_raw=with_raw)
    header = ["时间", "设备名称", "IP 地址", "结果", "耗时(秒)", "任务", "摘要 / 失败原因"]
    if with_raw:
        header.insert(6, "原始回显摘要")
    buffer = _io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        line = [row.get("created_at") or "", row.get("device_name") or "",
                row.get("device_ip") or "",
                "成功" if row.get("ok") else "失败",
                "%.1f" % ((row.get("duration_ms") or 0) / 1000.0),
                "#%s" % (row.get("run_id") or "")]
        if with_raw:
            line.append(row.get("raw_excerpt") or "")
            line.append(row.get("summary") if row.get("ok") else (row.get("reason") or ""))
        else:
            line.append(row.get("summary") if row.get("ok") else (row.get("reason") or ""))
        writer.writerow(line)
    return buffer.getvalue()


def overview(pending_only: bool = False) -> dict:
    """采集概览：设置 + 最近任务 + 设备凭据就绪情况。

    pending_only=True 时只返回尚未采集成功、仍在待采集区的设备，
    用于设备采集模块；采集成功后这些设备会从该模块消失并进入设备台账。
    """
    store = get_store()
    devices = store.devices()
    if pending_only:
        devices = [d for d in devices if d.get("pending_collection")]
    credentials = {c["ip"] for c in remote_login.credentials_list()}
    ready = [d for d in devices if d.get("ip") in credentials]
    runs = store.collect_runs(limit=50)
    logs = store.collect_logs(limit=200, with_raw=False)
    missing = [{"ip": d.get("ip"), "name": d.get("name") or d.get("ip")}
               for d in devices if d.get("ip") not in credentials]
    last_by_ip = store.last_collect_by_device()
    try:
        from .. import service
        views = {d["ip"]: d for d in service.devices_view(pending=pending_only)[0]}
    except Exception:
        views = {}
    device_rows = []
    for dev in devices:
        ip = dev.get("ip")
        if not ip:
            continue
        view = views.get(ip, {})
        last = last_by_ip.get(ip, {})
        device_rows.append({
            "ip": ip,
            "name": dev.get("name") or ip,
            "type_label": view.get("type_label") or nz.KIND_LABELS.get(dev.get("kind"), "其他设备"),
            "group": view.get("group") or dev.get("group") or "",
            "model": view.get("model") or dev.get("model") or "",
            "online": bool(dev.get("online")),
            "last_error": dev.get("last_error") or "",
            "last_checked_at": dev.get("last_checked_at") or "",
            "credential_ready": ip in credentials,
            "supported": is_supported(dev),
            "vendor": dev.get("vendor") or "",
            "vendor_display": dev.get("vendor_display") or dev.get("vendor") or "",
            "last_collect_at": last.get("created_at") or "",
            "last_ok": last.get("ok"),
            "last_result": (last.get("summary") or last.get("reason") or ""),
        })
    device_rows.sort(key=lambda d: (not d["credential_ready"], d["ip"]))

    # 变化检测告警（跟上一轮采集比出来的）：单独列出来，采集完一眼看到"这轮变化了什么"
    recent_changes = []
    try:
        for alert in store.alerts(limit=200):
            if not nz.is_change_metric(alert.get("metric")):
                continue
            recent_changes.append({
                "title": alert.get("content") or "",
                "device": alert.get("device") or alert.get("device_ip") or "",
                "device_ip": alert.get("device_ip") or "",
                "label": nz.change_metric_label(alert.get("metric")),
                "metric": alert.get("metric") or "",
                "severity": nz.severity_view(alert.get("severity"))[0],
                "time": alert.get("triggered_at") or "",
            })
            if len(recent_changes) >= 8:
                break
    except Exception:
        recent_changes = []

    return {
        "devices": device_rows,
        "settings": settings(),
        "devices_total": len(devices),
        "credential_ready": len(ready),
        "devices_supported": len([d for d in devices if is_supported(d)]),
        "credential_missing": len(devices) - len(ready),
        "missing_devices": missing[:50],
        "runs": runs,
        "last_run": runs[0] if runs else None,
        "last_logs": logs[:50],
        "stats": {"7d": store.collect_stats(7), "30d": store.collect_stats(30)},
        "change_alerts": recent_changes,
        "change_labels": nz.CHANGE_METRIC_LABELS,
        "running": _scheduler_state().get("running", False),
        "last_collect_at": (logs[0]["created_at"] if logs else ""),
        "vendor": "multi",
        "vendor_label": "华为 VRP + Linux/Windows 服务器",
        "commands": [cmd for _, cmd in huawei.COMMANDS] + huawei.PREPARE_COMMANDS
                    + [huawei.CONFIG_COMMAND + "（可选）"]
                    + ["uname / top / free / df / systemctl --failed / journalctl -p err（Linux）",
                       "Get-CimInstance / Get-Service / Get-WinEvent（Windows OpenSSH）"],
        "profiles": [
            {"key": "vrp", "label": "华为 VRP 交换机", "transport": "SSH 交互式 shell",
             "commands": [cmd for _, cmd in huawei.COMMANDS] + huawei.PREPARE_COMMANDS},
            {"key": "server", "label": "Linux / Windows 服务器", "transport": "SSH exec 通道",
             "commands": ["uname -srm", "cat /etc/os-release", "uptime", "top -bn1",
                          "free -m", "df -hT", "ip -br addr", "systemctl --failed",
                          "journalctl -p err", "ls -lt <备份目录>",
                          "Get-CimInstance / Get-Service / Get-WinEvent（Windows）"]},
        ],
    }