# -*- coding: utf-8 -*-
"""把采集/台账的原始记录归一化成页面直接可用的结构。

归一化的三件事：

1. **设备分类**：采集写入的设备记录不一定带 `category/kind`，
   所以按「型号 / 系统版本 / 厂商 / 角色」推断设备类型（交换机 / 路由器 / 防火墙 /
   无线控制器 / 服务器 / 其他），推断结果允许在台账里人工覆盖（`kind_override`）；
2. **健康度口径**：平台统一算分——巡检结论 + CPU / 内存阈值 + 接口错包 + 在线状态，
   满分 100，页面上的「健康度」「异常检查项」都由它派生，口径写在 `/api/system/meta`；
3. **时间格式**：采集记录给 ISO8601，页面沿用原型里的 `YYYY.MM.DD HH:mm`。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

KIND_LABELS = {
    "switch": "交换机",
    "core_switch": "核心交换机",
    "aggregation_switch": "汇聚交换机",
    "access_switch": "接入交换机",
    "router": "路由器",
    "firewall": "防火墙",
    "waf": "WAF",
    "ips": "IPS/IDS",
    "vpn": "VPN 设备",
    "security": "安全设备",
    "ac": "无线控制器",
    "server": "服务器",
    "other": "其他设备",
}

SERVER_HINTS = ("poweredge", "thinksystem", "uniserver", "proliant", "powerserver",
                "r750", "r4900", "sr650", "r740", "centos", "ubuntu", "red hat",
                "windows server", "linux", "vmware", "esxi")
FIREWALL_HINTS = ("secpath", "f1000", "usg", "firewall", "asa", "fortigate",
                  "ngfw", "f5000", "防火墙", "sangfor", "深信服", "天融信",
                  "奇安信", "山石", "绿盟", "安恒", "网神")
WAF_HINTS = ("waf", "web应用防火墙", "web 应用防火墙")
IPS_HINTS = ("ips", "ids", "入侵防御", "入侵检测")
VPN_HINTS = ("vpn", "ssl vpn", "ipsec vpn")
SECURITY_HINTS = FIREWALL_HINTS + WAF_HINTS + IPS_HINTS + VPN_HINTS + ("安全设备",)
ROUTER_HINTS = ("router", "msr", "ar ", "ne40", "cr16000")
AC_HINTS = ("wac", "ac6605", "wx", "无线控制器", "wireless")


def _text(*values) -> str:
    return " ".join(str(v).lower() for v in values if v)


# 命名习惯（CORE / AGG / ACC）在现网里比 role 字段更常见，作为型号之外的补充判据
NAME_HINTS = (("core", "core_switch"), ("agg", "aggregation_switch"),
              ("acc", "access_switch"))
CORE_MODEL_HINTS = ("s75", "s76", "s105", "s125", "s127", "s6800", "s6805",
                    "ce68", "ce88", "s12700")
AGG_MODEL_HINTS = ("s65", "s5560", "s6300", "s6800", "s6520", "catalyst 9",
                   "s5731", "s5732", "s6720")
#: 常见交换机型号族。用于识别“角色写防火墙、型号却是交换机”的字段冲突。
SWITCH_MODEL_HINTS = ("s5720", "s5731", "s5735", "s5560", "s6520", "s6720",
                      "s6800", "s12700", "ce68", "ce88", "catalyst", "nexus")


def model_role_warning(device: dict) -> str:
    """型号特征与角色 / 名称明显冲突时返回可展示的校验提示。"""
    model = _text(device.get("model"))
    label = _text(device.get("role"), device.get("name"), device.get("usage"))
    role_security = any(h in label for h in SECURITY_HINTS)
    role_switch = any(h in label for h in ("交换机", "switch", "核心", "汇聚", "接入"))
    model_security = any(h in model for h in SECURITY_HINTS)
    model_switch = any(h in model for h in SWITCH_MODEL_HINTS)
    if role_security and model_switch and not model_security:
        return "型号与角色不一致：角色指向安全设备，型号更像交换机（%s）" % (device.get("model") or "—")
    if role_switch and model_security and not model_switch:
        return "型号与角色不一致：角色指向交换机，型号更像安全设备（%s）" % (device.get("model") or "—")
    return ""


def infer_kind(device: dict, override: str = "") -> str:
    """推断设备类型：台账纠正 > role 字段 > 型号特征 > 命名特征 > 厂商兜底。

    采集到的设备记录不一定带 `category/kind`，所以这里有推断成分；推断结果在
    「设备清单 → 台账」里可以人工纠正（`ledger.kind_override`），纠正后以人工为准。
    """
    # “switch/other” 是台账里的粗分类，不应压过型号中的防火墙/WAF 特征；
    # 人工在台账补充里选择的细分类型仍然优先级最高。
    if override and override not in ("switch", "other"):
        return override
    role = (device.get("role") or "").lower()
    model = _text(device.get("model"))
    name = _text(device.get("name"))
    blob = _text(device.get("model"), device.get("version"), device.get("name"),
                device.get("group"), device.get("usage"), device.get("role"))

    if any(h in blob for h in WAF_HINTS):
        return "waf"
    if any(h in blob for h in IPS_HINTS):
        return "ips"
    if any(h in blob for h in VPN_HINTS):
        return "vpn"
    if any(h in blob for h in FIREWALL_HINTS):
        return "firewall"
    if any(h in blob for h in SERVER_HINTS):
        return "server"
    if any(h in blob for h in ROUTER_HINTS):
        return "router"
    if any(h in blob for h in AC_HINTS):
        return "ac"

    if role == "gateway" or any(h in model for h in CORE_MODEL_HINTS):
        return "core_switch"
    if role == "access":
        return "access_switch"
    for token, kind in NAME_HINTS:
        if token in name:
            return kind
    if any(h in model for h in AGG_MODEL_HINTS):
        return "aggregation_switch"
    if device.get("vendor") in ("h3c", "huawei", "cisco"):
        return "switch"
    return "other"


def kind_group(kind: str) -> str:
    """把细分类型归到页面用的三类：server / switch / other。"""
    if kind == "server":
        return "server"
    if kind in ("switch", "core_switch", "aggregation_switch", "access_switch",
                "router", "ac"):
        return "switch"
    if kind in ("firewall", "waf", "ips", "vpn", "security"):
        return "security"
    return "other"


def type_label(device: dict, kind: str) -> str:
    if kind in ("switch", "core_switch", "aggregation_switch", "access_switch"):
        role = (device.get("role") or "").lower()
        if role == "gateway":
            return "核心交换机"
        if role == "access":
            return "接入交换机"
        if kind != "switch":
            return KIND_LABELS.get(kind, "交换机")
        return "交换机"
    return KIND_LABELS.get(kind, "其他设备")


# ------------------------------------------------------------------ 时间
def fmt_time(value: str, pattern: str = "%Y.%m.%d %H:%M") -> str:
    dt = parse_time(value)
    return dt.strftime(pattern) if dt else ""


def parse_time(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("/", "-").replace("Z", "+00:00")
    for candidate in (text, text[:19], text[:16]):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    for pattern in ("%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M", "%Y.%m.%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def within(value, hours: int, now: datetime | None = None) -> bool:
    dt = parse_time(value)
    if dt is None:
        return False
    now = now or datetime.now()
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt >= (now - timedelta(hours=hours))


# ------------------------------------------------------------------ 健康度
def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# 阈值与交换机采集（display cpu-usage / memory-usage）的判定口径保持一致，
# 免得同一个数在采集日志里判「正常」、在页面判「偏高」。
CPU_WARN_PCT, CPU_ERR_PCT = 80.0, 90.0
MEM_WARN_PCT, MEM_ERR_PCT = 80.0, 90.0


def penalty(value, warn, danger, mid=5.0, high=10.0) -> float:
    if value is None:
        return 0.0
    if value >= danger:
        return high
    if value >= warn:
        return mid
    return 0.0


def health(device: dict, inspection: dict | None,
           monitor: dict | None = None) -> dict:
    """算出健康分与状态；没有巡检/监控数据时返回 unknown。"""
    inspection = inspection or {}
    monitor = monitor or {}
    if not inspection and not monitor:
        return {"score": None, "status": "unknown", "label": "未巡检",
                "tone": "muted", "reasons": [], "warnings": []}

    # 健康分只由当前平台的统一规则计算，不再直接采信历史记录里的自定义分数，
    # 避免出现“100 分 + 多项需关注”的口径冲突。
    score = 100.0
    reasons: list[str] = []
    warning = model_role_warning(device)
    if warning:
        score -= 8
        reasons.append(warning)
    if inspection:
        if not inspection.get("healthy", True):
            score -= 15
            reasons.append("巡检结论：异常")
        issues = (inspection.get("issues") or "").strip()
        if issues:
            count = len([p for p in re.split(r"[;；\n]+", issues) if p.strip()])
            score -= min(12.0, 4.0 * max(count, 1))
            reasons.append("巡检记录异常项 %d 条" % max(count, 1))
        errors = _num(inspection.get("error_total")) or 0
        if errors > 0:
            score -= min(10.0, 2.0 * errors)
            reasons.append("接口错包 %g" % errors)
        blocked = _num(inspection.get("stp_blocked"))
        if blocked:
            score -= min(8.0, 4.0 * blocked)
            reasons.append("STP 阻塞端口 %g" % blocked)
    if inspection.get("error"):
        score -= 10
        reasons.append("巡检执行异常：%s" % inspection["error"])

    cpu = _num(inspection.get("cpu"))
    memory = _num(inspection.get("memory"))
    if cpu is None:
        cpu = _num(monitor.get("cpu"))
    if memory is None:
        memory = _num(monitor.get("memory"))
    score -= penalty(cpu, CPU_WARN_PCT, CPU_ERR_PCT)
    score -= penalty(memory, MEM_WARN_PCT, MEM_ERR_PCT)
    if cpu is not None and cpu >= CPU_WARN_PCT:
        reasons.append("CPU 使用率 %g%% 偏高" % cpu)
    if memory is not None and memory >= MEM_WARN_PCT:
        reasons.append("内存使用率 %g%% 偏高" % memory)

    if not device.get("online", True):
        score -= 20
        reasons.append("设备当前离线")

    score = max(0.0, min(100.0, score))
    # 只要存在需关注原因，就不允许继续显示 100 / 正常；最高按 94 分进入“需关注”。
    if reasons and device.get("online", True):
        score = min(score, 94.0)
    if not device.get("online", True):
        status, label, tone = "danger", "离线", "danger"
    elif score >= 95:
        status, label, tone = "normal", "正常", "success"
    elif score >= 85:
        status, label, tone = "warning", "需关注", "warning"
    else:
        status, label, tone = "danger", "异常", "danger"
    return {"score": round(score, 1), "status": status, "label": label,
            "tone": tone, "reasons": reasons,
            "warnings": [warning] if warning else []}


def device_view(device: dict, inspection: dict | None = None,
                monitor: dict | None = None, ledger: dict | None = None) -> dict:
    """设备记录 → 页面用的设备台账行。"""
    ledger = ledger or {}
    # 类型的优先级：台账补充里的人工纠正 > 设备台账里的细分类型 > 按型号推断。
    # 台账里的 switch/other 只是粗分类，允许型号特征进一步识别为安全设备。
    manual = ledger.get("kind_override") or ""
    kind = infer_kind(device, manual or device.get("kind") or "")
    label = KIND_LABELS.get(manual) or type_label(device, kind)
    result = health(device, inspection, monitor)
    last_time = ""
    if inspection:
        last_time = inspection.get("inspected_at") or ""
    elif monitor:
        last_time = monitor.get("collected_at") or ""
    return {
        "id": device.get("id"),
        "ip": device.get("ip") or "",
        "name": device.get("name") or device.get("sysname") or device.get("ip") or "",
        "vendor": device.get("vendor") or "",
        "vendor_display": device.get("vendor_display") or device.get("vendor") or "",
        "model": device.get("model") or "",
        "serial": device.get("serial") or "",
        "version": device.get("version") or "",
        "role": device.get("role") or "",
        "group": device.get("group") or "",
        "region": device.get("region") or "",
        "online": bool(device.get("online", True)),
        "pending_collection": bool(device.get("pending_collection")),
        "port": device.get("port"),
        "last_online_at": device.get("last_online_at") or "",
        "last_checked_at": device.get("last_checked_at") or "",
        "last_error": device.get("last_error") or "",
        "updated_at": device.get("updated_at") or "",
        "kind": kind,
        "group_kind": kind_group(kind),
        "type_label": label,
        "health_score": result["score"],
        "health_status": result["status"],
        "health_label": result["label"],
        "health_tone": result["tone"],
        "health_reasons": result["reasons"],
        "validation_warnings": result.get("warnings") or [],
        "cpu": _num((inspection or {}).get("cpu")) if _num((inspection or {}).get("cpu")) is not None else _num((monitor or {}).get("cpu")),
        "memory": _num((inspection or {}).get("memory")) if _num((inspection or {}).get("memory")) is not None else _num((monitor or {}).get("memory")),
        "last_inspected_at": last_time,
        "last_inspected_text": fmt_time(last_time),
        "ledger": {
            "asset_no": ledger.get("asset_no", ""),
            "owner": ledger.get("owner", ""),
            "usage": ledger.get("usage", ""),
            "location": ledger.get("location", ""),
            "warranty_until": ledger.get("warranty_until", ""),
            "note": ledger.get("note", ""),
            "kind_override": ledger.get("kind_override", ""),
            "updated_at": ledger.get("updated_at", ""),
        },
    }


# 告警级别沿用 **syslog 风格数字**（0 最严重 → 7 最轻，见 alerting.py 的
# SEVERITY_CHOICES），这里统一折成平台的四档，页面与报表都用这一套。
#: 本平台自带采集的「变化检测」告警指标：跟该设备上一次采集比出来的变化，
#: 不是固定阈值命中（页面用 CHANGE_METRIC_LABELS 标出来，方便跟阈值告警区分）。
CHANGE_METRIC_LABELS = {
    "cpu_spike": "CPU 突增",
    "memory_spike": "内存突增",
    "port_down_new": "端口新变 down",
    "port_up": "端口恢复",
    "if_errors_growth": "错包快速增长",
    "stp_disabled": "STP 被禁用",
    "device_reboot": "设备重启",
    "cpu_sustained": "CPU 持续高位",
    "memory_sustained": "内存持续高位",
}


def is_change_metric(metric) -> bool:
    return str(metric or "") in CHANGE_METRIC_LABELS


def change_metric_label(metric) -> str:
    return CHANGE_METRIC_LABELS.get(str(metric or ""), "")


SEVERITY_MAP = {
    "0": ("critical", "紧急"),
    "1": ("critical", "告警"),
    "2": ("major", "严重"),
    "3": ("major", "错误"),
    "4": ("warning", "警告"),
    "5": ("info", "通知"),
    "6": ("info", "信息"),
    "7": ("info", "调试"),
}
# 已经是文字级别的（本平台自己的口径或第三方系统）原样保留
SEVERITY_TEXT = {
    "critical": ("critical", "紧急"), "major": ("major", "严重"),
    "warning": ("warning", "警告"), "warn": ("warning", "警告"),
    "info": ("info", "提示"), "error": ("major", "错误"),
    "notice": ("info", "通知"), "debug": ("info", "调试"),
}


def severity_view(value) -> tuple[str, str]:
    """告警级别值 → (四档键, 中文标签)。"""
    raw = str(value if value is not None else "").strip().lower()
    if raw in SEVERITY_MAP:
        return SEVERITY_MAP[raw]
    if raw in SEVERITY_TEXT:
        return SEVERITY_TEXT[raw]
    return "info", (raw or "未分级")


def metric_value(metrics: list, device_id, keywords: tuple) -> float | None:
    """从遥测指标里挑一个值：同设备、同关键词、取最新一条。"""
    best, best_time = None, ""
    for item in metrics or []:
        if device_id is not None and item.get("device_id") not in (device_id, None):
            continue
        blob = _text(item.get("metric"), item.get("label"))
        if not any(k in blob for k in keywords):
            continue
        value = _num(item.get("value"))
        if value is None:
            continue
        stamp = str(item.get("collected_at") or "")
        if value is not None and stamp >= best_time:
            best, best_time = value, stamp
    return best

