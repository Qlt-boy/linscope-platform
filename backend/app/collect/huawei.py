# -*- coding: utf-8 -*-
"""华为 VRP 交换机采集：命令清单 + 回显解析（只用只读 display 命令）。

设计要点：

* **只读**：全部是 `display` 命令，不做任何配置变更（与平台定位一致）；
* **容错解析**：不同 VRP 版本回显细节不一样（V200R005 / R019 / R021…），解析器一律用
  「找关键字 + 正则」的宽容写法，解析不到的字段给 None，由上层如实显示「未采集」，
  **绝不编数**；
* **可测**：解析函数是纯函数，`backend/tools/fake_huawei_switch.py` 提供同格式回显，
  端到端可验证（见 `backend/tools/collect_selftest.py`）。
"""
from __future__ import annotations

import re

#: 采集命令清单：key 为内部字段名，值是 VRP 命令（顺序即执行顺序）
COMMANDS = [
    ("version", "display version"),
    ("sysname", "display current-configuration | include sysname"),
    ("serial", "display device manuinfo"),
    ("cpu", "display cpu-usage"),
    ("memory", "display memory-usage"),
    ("interfaces", "display interface"),
    ("stp", "display stp brief"),
    ("lldp", "display lldp neighbor"),
    ("alarm", "display alarm"),
]

#: 配置备份命令（单独开关：内容可能几百 KB，按需采集）
CONFIG_COMMAND = "display current-configuration"

#: 登录后先关分屏，否则回显会被 `---- More ----` 截断
PREPARE_COMMANDS = ["screen-length 0 temporary"]

MODEL_RE = re.compile(r"(?:^|\n)\s*(HUAWEI\s+)?([A-Za-z]*S\d{4}[A-Za-z0-9\-]*)\s+"
                      r"(?:Routing\s+Switch|Switch|Router)", re.I)
VERSION_RE = re.compile(r"VRP\s*\(R\)\s*software,\s*Version\s+([^\r\n(]+)"
                        r"(?:\(([^)]*)\))?", re.I)
UPTIME_RE = re.compile(r"uptime is\s+(.+)", re.I)
BOARD_RE = re.compile(r"Board\s+Type\s*:\s*(\S+)", re.I)
SERIAL_RE = re.compile(r"(?:Device\s+Serial\s+Number|Board\s+Serial\s+number)\s*:?\s*"
                       r"([A-Za-z0-9\-]+)", re.I)
CPU_FIVE_RE = re.compile(r"CPU utilization for five seconds:\s*(\d+(?:\.\d+)?)\s*%", re.I)
CPU_SIMPLE_RE = re.compile(r"CPU Usage\s*:\s*(\d+(?:\.\d+)?)\s*%", re.I)
CPU_MAX_RE = re.compile(r"CPU Usage\s*:\s*\d+(?:\.\d+)?\s*%\s*Max:\s*(\d+(?:\.\d+)?)\s*%", re.I)
MEM_RE = re.compile(r"Total Used Memory:\s*\d+\s*MB\s*\((\d+(?:\.\d+)?)\s*%\)", re.I)
MEM_TOTAL_RE = re.compile(r"System Total Memory:\s*(\d+)\s*MB", re.I)
STP_PORT_RE = re.compile(r"^\s*\d+\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$", re.M)
ALARM_LINE_RE = re.compile(r"^(0x[0-9a-fA-F]+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})"
                           r"\s+(\S+)\s+(.+)$", re.M)
INTF_HEAD_RE = re.compile(r"^(\S+)\s+current state\s*:\s*(\S+)", re.M)
INTF_PROTO_RE = re.compile(r"^\s*Line protocol current state\s*:\s*(\S+)", re.M)
INTF_CRC_RE = re.compile(r"CRC:\s*(\d+)", re.I)
INTF_ERRORS_RE = re.compile(r"Errors:\s*(\d+)", re.I)
INTF_DESC_RE = re.compile(r"Description:[ \t]*(.*)", re.I)
SYSNAME_RE = re.compile(r"^\s*sysname\s+(\S+)", re.M | re.I)


def _num(text) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_version(output: str) -> dict:
    """`display version` → 型号 / 版本 / 运行时长 / 补丁。"""
    output = output or ""
    model, version, patch, uptime = "", "", "", ""
    match = MODEL_RE.search(output)
    if match:
        model = match.group(2)
    match = VERSION_RE.search(output)
    if match:
        version = match.group(1).strip()
        patch = (match.group(2) or "").strip()
    match = UPTIME_RE.search(output)
    if match:
        uptime = match.group(1).strip()
    if not model:
        match = BOARD_RE.search(output)
        if match:
            model = match.group(1)
    return {"model": model, "version": f"VRP {version}".strip(),
            "patch": patch, "uptime": uptime}


def parse_sysname(output: str) -> str:
    match = SYSNAME_RE.search(output or "")
    return match.group(1).strip() if match else ""


def parse_serial(output: str) -> str:
    match = SERIAL_RE.search(output or "")
    return match.group(1) if match else ""


def parse_cpu(output: str) -> dict:
    """CPU 使用率：优先取「five seconds」，退化到 `CPU Usage : N%`。"""
    output = output or ""
    value = _num((CPU_FIVE_RE.search(output) or [None, None])[1]) if CPU_FIVE_RE.search(output) else None
    if value is None:
        match = CPU_SIMPLE_RE.search(output)
        value = _num(match.group(1)) if match else None
    match = CPU_MAX_RE.search(output)
    return {"cpu": value, "cpu_max": _num(match.group(1)) if match else None}


def parse_memory(output: str) -> dict:
    output = output or ""
    match = MEM_RE.search(output)
    used = _num(match.group(1)) if match else None
    match = MEM_TOTAL_RE.search(output)
    return {"memory": used, "memory_total_mb": _num(match.group(1)) if match else None}


def parse_interfaces(output: str) -> list:
    """`display interface` → 每个端口的 up/down、CRC、Errors。"""
    output = output or ""
    ports = []
    heads = list(INTF_HEAD_RE.finditer(output))
    for index, head in enumerate(heads):
        name, state = head.group(1), head.group(2)
        block = output[head.end(): heads[index + 1].start() if index + 1 < len(heads) else len(output)]
        proto = INTF_PROTO_RE.search(block)
        crc = INTF_CRC_RE.search(block)
        errors = INTF_ERRORS_RE.search(block)
        desc = INTF_DESC_RE.search(block)
        ports.append({
            "name": name,
            "phy_state": state.upper(),
            "proto_state": (proto.group(1).upper() if proto else ""),
            "up": state.upper() == "UP",
            "crc": _num(crc.group(1)) if crc else None,
            "errors": _num(errors.group(1)) if errors else None,
            "description": (desc.group(1).strip() if desc else ""),
        })
    return ports


LLDP_ROW_RE = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s*$", re.M)


def parse_lldp(output: str) -> list:
    """`display lldp neighbor` → 邻居表（本端口 / 邻居设备 / 邻居口 / 存活秒数）。

    不同 VRP 版本的列名有差异（Local Intf / Local interface），但数据行都是
    「本端口 邻居设备 邻居口 存活时间」四列，按这个形状取。
    """
    rows = []
    for match in LLDP_ROW_RE.finditer(output or ""):
        local, device, port, ttl = match.groups()
        if local.lower().startswith("local") or local.startswith("-"):
            continue
        rows.append({"local_port": local, "neighbor_name": device,
                     "neighbor_port": port, "neighbor_ip": "",
                     "ttl": int(ttl)})
    return rows


def parse_stp(output: str) -> dict:
    """`display stp brief` → 启用状态 + 转发/阻塞端口数。"""
    output = output or ""
    rows = [m for m in STP_PORT_RE.finditer(output)
            if m.group(2).upper() in ("ROOT", "DESI", "ALTE", "BACK", "MSTR", "DISA")]
    states = [m.group(3).upper() for m in rows]
    if not rows:
        text = output.strip()
        return {"stp_state": "disabled" if not text else "unknown",
                "stp_forward": None, "stp_blocked": None, "ports": []}
    return {
        "stp_state": "enabled",
        "stp_forward": len([s for s in states if s in ("FORWARDING", "LEARNING")]),
        "stp_blocked": len([s for s in states if s in ("DISCARDING", "BLOCKING")]),
        "ports": [{"port": m.group(1), "role": m.group(2), "state": m.group(3)}
                  for m in rows],
    }


def parse_alarms(output: str) -> list:
    alarms = []
    for match in ALARM_LINE_RE.finditer(output or ""):
        alarms.append({"id": match.group(1), "date": match.group(2),
                       "time": match.group(3), "severity": match.group(4),
                       "info": match.group(5).strip()})
    return alarms


def parse_config(output: str) -> str:
    return (output or "").strip()


def uptime_to_seconds(text: str) -> int | None:
    """`uptime is 123 days, 4 hours, 5 minutes` → 秒数（变化检测判"设备重启"用）。"""
    if not text:
        return None
    days = re.search(r"(\d+)\s*day", text, re.I)
    hours = re.search(r"(\d+)\s*hour", text, re.I)
    minutes = re.search(r"(\d+)\s*minute", text, re.I)
    if not (days or hours or minutes):
        return None
    return ((int(days.group(1)) if days else 0) * 86400
            + (int(hours.group(1)) if hours else 0) * 3600
            + (int(minutes.group(1)) if minutes else 0) * 60)


#: 采集结果 → 归一化记录（写库用）
def build_records(raw: dict, device: dict) -> dict:
    """把原始回显解析成：设备信息 / 巡检记录 / 监控记录 / 告警 / 配置备份。"""
    version = parse_version(raw.get("version", ""))
    serial = parse_serial(raw.get("serial", "")) or device.get("serial") or ""
    sysname = parse_sysname(raw.get("sysname", "")) or device.get("hostname") or ""
    cpu = parse_cpu(raw.get("cpu", ""))
    memory = parse_memory(raw.get("memory", ""))
    ports = parse_interfaces(raw.get("interfaces", ""))
    stp = parse_stp(raw.get("stp", ""))
    lldp = parse_lldp(raw.get("lldp", ""))
    alarms = parse_alarms(raw.get("alarm", ""))

    down_ports = [p for p in ports if not p["up"]]
    err_ports = [p for p in ports if (p.get("crc") or 0) > 0 or (p.get("errors") or 0) > 0]
    error_total = sum(int(p.get("crc") or 0) + int(p.get("errors") or 0) for p in err_ports)

    issues = []
    if cpu["cpu"] is not None and cpu["cpu"] >= 90:
        issues.append("CPU 使用率 %.0f%% 过高" % cpu["cpu"])
    elif cpu["cpu"] is not None and cpu["cpu"] >= 80:
        issues.append("CPU 使用率 %.0f%% 偏高" % cpu["cpu"])
    if memory["memory"] is not None and memory["memory"] >= 90:
        issues.append("内存使用率 %.0f%% 过高" % memory["memory"])
    elif memory["memory"] is not None and memory["memory"] >= 80:
        issues.append("内存使用率 %.0f%% 偏高" % memory["memory"])
    if stp["stp_state"] == "disabled":
        issues.append("STP 未启用（存在环路风险）")
    if err_ports:
        issues.append("%d 个接口存在错误包（共 %d 个）" % (len(err_ports), error_total))
    if down_ports:
        issues.append("%d 个端口 down：%s"
                      % (len(down_ports), "、".join(p["name"] for p in down_ports[:4])))

    inspection = {
        "device_cpu": cpu["cpu"],
        "device_memory": memory["memory"],
        "stp_state": stp["stp_state"],
        "stp_mode": "",
        "stp_forward": stp["stp_forward"],
        "stp_blocked": stp["stp_blocked"],
        "error_ports": len(err_ports),
        "error_total": error_total,
        "healthy": not [i for i in issues if ("过高" in i or "未启用" in i)],
        "issues": "；".join(issues),
    }
    monitor = {
        "sysname": sysname or device.get("name") or "",
        "serial": serial,
        "version": version["version"],
        "cpu": cpu["cpu"],
        "memory": memory["memory"],
        "ok": True,
        "error": "",
    }
    alerts = []
    for port in down_ports[:10]:
        alerts.append({"source": "monitor", "severity": "4", "metric": "port_down",
                       "content": "端口 %s 处于 down 状态（%s）"
                                  % (port["name"], port.get("description") or "无描述"),
                       # 去重键到端口级：错包计数每轮都在涨，按内容去重会每轮刷屏
                       "dedupe_key": "port_down:%s" % port["name"], "value": None})
    for port in err_ports[:10]:
        crc, errors = int(port.get("crc") or 0), int(port.get("errors") or 0)
        alerts.append({"source": "monitor", "severity": "4", "metric": "if_errors",
                       "content": "端口 %s 存在错误包（CRC %d / Errors %d）"
                                  % (port["name"], crc, errors),
                       "dedupe_key": "if_errors:%s" % port["name"],
                       "value": crc + errors})
    for alarm in alarms[:10]:
        alerts.append({"source": "syslog", "severity": "2", "metric": "device_alarm",
                       "content": "设备告警[%s] %s" % (alarm["severity"], alarm["info"]),
                       "dedupe_key": "device_alarm:%s" % alarm["info"], "value": None})

    return {
        "device": {"name": sysname,
                   "model": version["model"] or device.get("model") or "",
                   "serial": serial, "version": version["version"]},
        "inspection": inspection,
        "monitor": monitor,
        "alerts": alerts,
        "ports": ports,
        "stp": stp,
        "lldp": lldp,
        "uptime": version["uptime"],
        # 变化检测（设备重启）要用秒数，存下来免得每轮重新解析
        "uptime_seconds": uptime_to_seconds(version["uptime"]),
    }