# -*- coding: utf-8 -*-
"""服务器采集（SSH，只读）：Linux / Windows(OpenSSH)。

设计要点：

* **只跑只读命令**：uname / top / free / df / systemctl --failed / journalctl -p err /
  Get-CimInstance / Get-Service / Get-WinEvent …，不做任何变更；
* **按「报告里的检查项」分桶**：os / cpu / memory / disk / net / service / log / temp / backup，
  每桶可串多条命令；留档时拼成真实终端样式（$ 命令 / PS> 命令），
  报告直接按桶渲染成一张命令回显截图，键名与 docreport 的 SERVER_COMMANDS 一致；
* **解析容错**：不同发行版 / 不同 PowerShell 版本输出差异很大，解析不到就给 None，
  页面与报告照实显示「未采集」，不编数；
* **纯函数**：解析函数不碰网络与数据库，可用样例回显单独验证。
"""
from __future__ import annotations

import posixpath
import re
import stat as statmod
import time

#: 每个检查项要跑的命令：(命令说明, 实际命令, 解析用的稳定键)
LINUX_BUCKETS = [
    ("os", [
        ("uname", "uname -srm", "uname -srm"),
        ("os-release", "cat /etc/os-release 2>/dev/null", "os_release"),
        ("hostname", "hostname", "hostname"),
        ("dmi", "cat /sys/class/dmi/id/sys_vendor /sys/class/dmi/id/product_name "
                "/sys/class/dmi/id/product_serial 2>/dev/null",
         "dmi"),
        ("uptime", "uptime", "uptime"),
    ]),
    ("cpu", [("top", "top -bn1 2>/dev/null | head -n 12", "top")]),
    ("memory", [("free", "free -m 2>/dev/null || cat /proc/meminfo", "free")]),
    ("disk", [("df", "df -hT -x tmpfs -x devtmpfs -x overlay 2>/dev/null", "df")]),
    ("net", [("ip", "ip -br addr 2>/dev/null || ifconfig -a 2>/dev/null", "ip")]),
    ("service", [("systemctl", "systemctl --failed --no-pager 2>/dev/null", "systemctl")]),
    ("log", [("journalctl", "journalctl -p err -n 20 --no-pager 2>/dev/null", "journalctl")]),
    ("temp", [("thermal", "for f in /sys/class/thermal/thermal_zone*/temp; do "
                          "test -r \"$f\" && echo \"$f $(cat $f)\"; done 2>/dev/null",
               "thermal")]),
    ("backup", [("backup", "ls -lt <PATH> 2>/dev/null | head -n 12", "backup")]),
]

WINDOWS_BUCKETS = [
    ("os", [
        ("os", "Get-CimInstance Win32_OperatingSystem | ForEach-Object { "
               "'Caption ' + $_.Caption; 'Version ' + $_.Version; "
               "'BuildNumber ' + $_.BuildNumber }; "
               "Get-CimInstance Win32_ComputerSystem | ForEach-Object { "
               "'Manufacturer ' + $_.Manufacturer; 'Model ' + $_.Model }", "win-os"),
        ("hostname", "hostname", "hostname"),
        ("uptime", "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime",
         "win-uptime"),
    ]),
    ("cpu", [
        ("cpu", "Get-CimInstance Win32_Processor | ForEach-Object { "
                "'Name ' + $_.Name; 'LoadPercentage ' + $_.LoadPercentage; "
                "'NumberOfLogicalProcessors ' + $_.NumberOfLogicalProcessors }", "win-cpu"),
    ]),
    ("memory", [
        ("memory", "Get-CimInstance Win32_OperatingSystem | ForEach-Object { "
                   "'TotalVisibleMemorySize ' + $_.TotalVisibleMemorySize; "
                   "'FreePhysicalMemory ' + $_.FreePhysicalMemory }", "win-memory"),
    ]),
    ("disk", [
        ("disk", "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object { "
                 "$_.DeviceID + ' ' + $_.Size + ' ' + $_.FreeSpace }", "win-disk"),
    ]),
    ("net", [
        ("net", "Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { "
                "$_.InterfaceAlias + ' ' + $_.IPAddress + '/' + $_.PrefixLength }", "win-net"),
    ]),
    ("service", [
        ("service", "Get-Service | Where-Object { $_.Status -ne 'Running' } | ForEach-Object { "
                    "$_.Name + ' ' + $_.Status }", "win-service"),
    ]),
    ("log", [
        ("log", "Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2} -MaxEvents 20 "
                "-ErrorAction SilentlyContinue | ForEach-Object { "
                "$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss') + ' ' + $_.Id + ' ' + "
                "$_.LevelDisplayName }", "win-log"),
    ]),
    ("backup", [
        ("backup", "Get-ChildItem '<PATH>' -ErrorAction SilentlyContinue | "
                   "Sort-Object LastWriteTime -Descending | Select-Object -First 12 | "
                   "ForEach-Object { $_.Name + ' ' + $_.Length + ' ' + "
                   "$_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') }", "win-backup"),
    ]),
]

#: 备份目录默认值（可在「采集设置」里覆盖）
DEFAULT_BACKUP_PATH = {"linux": "/var/backups", "windows": "C:\\Backup"}
#: 打包下载服务器备份时的安全上限（全部在内存中完成，避免大盘拖垮服务）
BACKUP_MAX_FILES = 200
BACKUP_MAX_FILE_BYTES = 50 * 1024 * 1024
BACKUP_MAX_TOTAL_BYTES = 128 * 1024 * 1024
BACKUP_MAX_DEPTH = 5
BACKUP_SKIP_EXT = {".log", ".tmp", ".swp", ".lock", ".pid"}


class BackupReadError(Exception):
    """读取服务器备份目录失败（目录不存在、无权限、SFTP 不可用等）。"""


def _backup_sftp_path(path: str, os_type: str) -> str:
    path = (path or "").strip()
    if not path:
        path = DEFAULT_BACKUP_PATH.get(os_type, "")
    if os_type == "windows":
        path = path.replace("\\", "/")
    return path.rstrip("/") or "/"


def read_backup_files(client, os_type: str, backup_path: str = "",
                      timeout: float = 25.0) -> dict:
    """通过 SFTP 读取服务器备份目录中的原始文件（不落本机磁盘）。

    返回 ``{"path": 远端绝对路径, "files": [{"path": 相对路径, "data": bytes}],
    "errors": [...]}``。目录内的子目录会递归读取；符号链接跳过，避免越界。
    """
    root = _backup_sftp_path(backup_path, os_type)
    sftp = None
    files = []
    errors = []
    total = 0
    try:
        sftp = client.open_sftp()
        try:
            sftp.get_channel().settimeout(timeout)
        except Exception:                                  # noqa: BLE001
            pass
        try:
            root = sftp.normalize(root) or root
        except Exception:                                  # noqa: BLE001
            pass
        try:
            root_stat = sftp.stat(root)
        except Exception as exc:                           # noqa: BLE001
            raise BackupReadError("备份目录不可访问（%s）：%s" % (root, exc))
        if not statmod.S_ISDIR(root_stat.st_mode or 0):
            raise BackupReadError("备份路径不是目录：%s" % root)

        def walk(remote_dir: str, rel_dir: str, depth: int) -> None:
            nonlocal total
            if len(files) >= BACKUP_MAX_FILES:
                errors.append("文件数量超过 %d 个，已截断" % BACKUP_MAX_FILES)
                return
            try:
                attrs = sftp.listdir_attr(remote_dir)
            except Exception as exc:                       # noqa: BLE001
                errors.append("目录不可读（%s）：%s" % (remote_dir, exc))
                return
            for attr in sorted(attrs, key=lambda a: a.filename):
                name = attr.filename
                if name in (".", "..") or name.startswith("."):
                    continue
                remote = posixpath.join(remote_dir, name)
                rel = posixpath.join(rel_dir, name) if rel_dir else name
                mode = attr.st_mode or 0
                if statmod.S_ISLNK(mode):
                    errors.append("跳过符号链接：%s" % rel)
                    continue
                if statmod.S_ISDIR(mode):
                    if depth < BACKUP_MAX_DEPTH:
                        walk(remote, rel, depth + 1)
                    else:
                        errors.append("目录层级超过 %d，已跳过：%s" % (BACKUP_MAX_DEPTH, rel))
                    continue
                if not statmod.S_ISREG(mode):
                    continue
                ext = posixpath.splitext(name)[1].lower()
                if ext in BACKUP_SKIP_EXT:
                    continue
                size = int(attr.st_size or 0)
                if size > BACKUP_MAX_FILE_BYTES:
                    errors.append("单文件超过 50MB，已跳过：%s" % rel)
                    continue
                if total + size > BACKUP_MAX_TOTAL_BYTES:
                    errors.append("备份总大小超过 128MB，后续文件已跳过")
                    return
                try:
                    with sftp.open(remote, "rb") as handle:
                        data = handle.read(BACKUP_MAX_FILE_BYTES + 1)
                except Exception as exc:                   # noqa: BLE001
                    errors.append("读取失败（%s）：%s" % (rel, exc))
                    continue
                if len(data) > BACKUP_MAX_FILE_BYTES:
                    errors.append("单文件超过 50MB，已跳过：%s" % rel)
                    continue
                files.append({"path": rel, "data": data})
                total += len(data)
                if len(files) >= BACKUP_MAX_FILES:
                    errors.append("文件数量超过 %d 个，已截断" % BACKUP_MAX_FILES)
                    return

        walk(root, "", 1)
        return {"path": root, "files": files, "errors": errors}
    except BackupReadError:
        raise
    except Exception as exc:                               # noqa: BLE001
        raise BackupReadError("SFTP 读取备份目录失败：%s: %s"
                              % (type(exc).__name__, exc))
    finally:
        if sftp is not None:
            try:
                sftp.close()
            except Exception:                              # noqa: BLE001
                pass

#: 每个桶留档的字符上限
RAW_KEEP = {"os": 1500, "cpu": 900, "memory": 700, "disk": 1200, "net": 900,
            "service": 700, "log": 1200, "temp": 400, "backup": 700}


# ---------------------------------------------------------------- 小工具
def _lines(text) -> list:
    return [line.rstrip() for line in
            (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(text) -> str:
    for line in _lines(text):
        if line.strip():
            return line.strip()
    return ""


def _out(raw: dict, key: str, tag: str) -> str:
    """取某桶里某条命令的原始输出（解析只用原始输出，不用带提示符的截图文本）。

    键是 (桶, tag)，tag 在命令清单里固定写死，不随命令文本调整而变。
    """
    return (((raw or {}).get(key) or {}).get(tag) or "").strip()


def build_echo(buckets, outputs: dict, os_type: str) -> dict:
    """把每条命令的回显拼成终端样式：命令行 + 输出。"""
    prompt = "PS C:\\>" if os_type == "windows" else "$"
    echo = {}
    for key, steps in buckets:
        chunks = []
        for _label, command, tag in steps:
            text = (((outputs or {}).get(key) or {}).get(tag) or "").strip()
            if not text:
                continue
            shown = command if len(command) <= 150 else command[:147] + "…"
            chunks.append("%s %s\n%s" % (prompt, shown, text))
        if chunks:
            echo[key] = "\n\n".join(chunks)
    return echo


def raw_excerpt(echo: dict) -> str:
    """把分桶回显裁剪成 collect_logs.raw_excerpt（格式与交换机采集一致）。"""
    parts = []
    for key, limit in RAW_KEEP.items():
        text = (echo or {}).get(key) or ""
        if not text.strip():
            continue
        body = text.strip()
        if len(body) > limit:
            body = body[:limit] + "\n…（截断，完整回显未留存）"
        parts.append("──── %s ────\n%s" % (key, body))
    return "\n".join(parts)[:8000]


# ---------------------------------------------------------------- Linux 解析
CPU_IDLE_RE = re.compile(r"([\d.]+)\s*id\b")
CPU_US_RE = re.compile(r"%Cpu\(s\):\s*([\d.]+)\s*us")
MEM_LINE_RE = re.compile(r"^Mem:\s+(\d+)\s+(\d+)", re.M)
MEMINFO_TOTAL_RE = re.compile(r"MemTotal:\s+(\d+)\s*kB", re.I)
MEMINFO_AVAIL_RE = re.compile(r"MemAvailable:\s+(\d+)\s*kB", re.I)
DF_LINE_RE = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)%\s+(\S+)", re.M)
FAILED_UNIT_RE = re.compile(r"^\s*\S+\.\w+\s+loaded\s+failed\b", re.M)
UPTIME_RE = re.compile(r"up\s+(.+?),\s+\d+\s+users?", re.I)
UPTIME_ALT_RE = re.compile(r"up\s+(.+?),\s+load average", re.I)
THERMAL_RE = re.compile(r"(\d{3,6})")


def parse_linux_cpu(text: str):
    match = CPU_IDLE_RE.search(text or "")
    if match:
        return round(100.0 - float(match.group(1)), 1)
    match = CPU_US_RE.search(text or "")
    return _num(match.group(1)) if match else None


def parse_linux_memory(text: str):
    text = text or ""
    match = MEM_LINE_RE.search(text)
    if match:
        total, used = float(match.group(1)), float(match.group(2))
        return round(100.0 * used / total, 1) if total else None
    total_match = MEMINFO_TOTAL_RE.search(text)
    avail_match = MEMINFO_AVAIL_RE.search(text)
    if total_match and avail_match:
        total = float(total_match.group(1))
        available = float(avail_match.group(1))
        return round(100.0 * (total - available) / total, 1) if total else None
    return None


def parse_linux_disk(text: str):
    """返回 (最高使用率, 根分区使用率, [(挂载点, 使用率), ...])。"""
    best = None
    root = None
    rows = []
    for match in DF_LINE_RE.finditer(text or ""):
        use = _num(match.group(6))
        mount = match.group(7)
        if use is None:
            continue
        rows.append((mount, use))
        best = use if best is None else max(best, use)
        if mount == "/":
            root = use
    return best, root, rows


def parse_linux_temp(text: str):
    values = []
    for match in THERMAL_RE.finditer(text or ""):
        raw = float(match.group(1))
        value = raw / 1000.0 if raw > 1000 else raw
        if -40 <= value <= 150:
            values.append(value)
    return round(max(values), 1) if values else None


def parse_uptime(text: str):
    """uptime 文本 → (可读运行时长, 秒)。"""
    line = _first(text)
    match = UPTIME_RE.search(line) or UPTIME_ALT_RE.search(line)
    body = match.group(1).strip() if match else ""
    return body, _uptime_seconds(body)


def _uptime_seconds(text: str):
    """12 days, 3:21 / 3 days, 4 hours, 5 minutes → 秒。"""
    if not text:
        return None
    days = re.search(r"(\d+)\s*day", text, re.I)
    hours = re.search(r"(\d+)\s*hour", text, re.I)
    minutes = re.search(r"(\d+)\s*minute", text, re.I)
    clock = re.search(r"(\d+):(\d+)", text)
    if not (days or hours or minutes or clock):
        return None
    total = ((int(days.group(1)) if days else 0) * 86400
             + (int(hours.group(1)) if hours else 0) * 3600
             + (int(minutes.group(1)) if minutes else 0) * 60)
    if clock:
        # uptime 的 "3:21" 是 小时:分钟（不是 分:秒）
        total += int(clock.group(1)) * 3600 + int(clock.group(2)) * 60
    return total


def parse_linux(raw: dict, device: dict) -> dict:
    uname = _first(_out(raw, "os", "uname"))
    release = _out(raw, "os", "os_release")
    host = _first(_out(raw, "os", "hostname"))
    dmi = [line.strip() for line in _lines(
        _out(raw, "os", "dmi"))
        if line.strip()]
    vendor = dmi[0] if len(dmi) > 0 else ""
    model = dmi[1] if len(dmi) > 1 else ""
    serial = dmi[2] if len(dmi) > 2 else ""
    pretty = ""
    match = re.search(r'PRETTY_NAME="?([^"\n]+)"?', release)
    if match:
        pretty = match.group(1).strip()

    uptime_text, uptime_seconds = parse_uptime(_out(raw, "os", "uptime"))
    disk_best, disk_root, disk_rows = parse_linux_disk(_out(raw, "disk", "df"))

    service_text = _out(raw, "service", "systemctl")
    if "0 loaded units listed" in service_text:
        failed_services = 0
    elif service_text.strip():
        failed_services = len(FAILED_UNIT_RE.findall(service_text))
    else:
        failed_services = None

    log_text = _out(raw, "log", "journalctl")
    if "No entries" in log_text:
        log_errors = 0
    elif log_text.strip():
        log_errors = len([line for line in _lines(log_text)
                          if line.strip() and not line.startswith("-- ")])
    else:
        log_errors = None

    return {
        "os_name": pretty or uname or "Linux",
        "kernel": uname,
        "hostname": host or device.get("name") or device.get("ip") or "",
        "vendor": vendor or device.get("vendor_display") or "",
        "model": model or device.get("model") or "",
        "serial": serial or device.get("serial") or "",
        "version": pretty or uname,
        "cpu": parse_linux_cpu(_out(raw, "cpu", "top")),
        "memory": parse_linux_memory(_out(raw, "memory", "free")),
        "disk": disk_best, "disk_root": disk_root, "disk_rows": disk_rows,
        "temp": parse_linux_temp(_out(raw, "temp", "thermal")),
        "uptime": uptime_text, "uptime_seconds": uptime_seconds,
        "failed_services": failed_services, "log_errors": log_errors,
        "backups": None,
    }


# ---------------------------------------------------------------- Windows 解析
def _kv_lines(text: str) -> dict:
    """把 'Key 值' 行解析成字典（PowerShell 自定义输出，避免依赖 Format-Table 对齐）。"""
    out = {}
    for line in _lines(text):
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2:
            out[parts[0]] = parts[1].strip()
    return out


def parse_windows_uptime(text: str):
    line = _first(text)
    match = re.match(r"(?:(\d+)\.)?(\d+):(\d+):(\d+)", line or "")
    if match:
        days = int(match.group(1) or 0)
        seconds = (days * 86400 + int(match.group(2)) * 3600
                   + int(match.group(3)) * 60 + int(match.group(4)))
        label = ("%d 天 %s:%s:%s" % (days, match.group(2), match.group(3), match.group(4))
                 if days else "%s:%s:%s" % (match.group(2), match.group(3), match.group(4)))
        return label, seconds
    kv = _kv_lines(text)
    if kv.get("Days") or kv.get("Hours"):
        days = int(_num(kv.get("Days")) or 0)
        hours = int(_num(kv.get("Hours")) or 0)
        minutes = int(_num(kv.get("Minutes")) or 0)
        label = "%d 天 %d 小时 %d 分" % (days, hours, minutes)
        return label, days * 86400 + hours * 3600 + minutes * 60
    return "", None


def parse_windows(raw: dict, device: dict) -> dict:
    kv = _kv_lines(_out(raw, "os", "win-os"))
    host = _first(_out(raw, "os", "hostname"))
    version = " ".join(x for x in (kv.get("Caption"), kv.get("Version")) if x)

    loads = [float(x) for x in re.findall(r"LoadPercentage\s+(\d+)",
                                          _out(raw, "cpu", "win-cpu"))]
    cpu = round(max(loads), 1) if loads else None

    mem_kv = _kv_lines(_out(raw, "memory", "win-memory"))
    total = _num(mem_kv.get("TotalVisibleMemorySize"))
    free = _num(mem_kv.get("FreePhysicalMemory"))
    memory = round(100.0 * (total - free) / total, 1) if total and free is not None else None

    disk_best = None
    disk_rows = []
    for line in _lines(_out(raw, "disk", "win-disk")):
        parts = line.split()
        if len(parts) < 3:
            continue
        size, free_space = _num(parts[1]), _num(parts[2])
        if not size or free_space is None:
            continue
        use = round(100.0 * (size - free_space) / size, 1)
        disk_rows.append((parts[0], use))
        disk_best = use if disk_best is None else max(disk_best, use)

    uptime_text, uptime_seconds = parse_windows_uptime(
        _out(raw, "uptime", "win-uptime"))
    service_text = _out(raw, "service", "win-service")
    log_text = _out(raw, "log", "win-log")
    backup_text = _out(raw, "backup", "win-backup")

    return {
        "os_name": kv.get("Caption") or version or "Windows",
        "kernel": version,
        "hostname": host or device.get("name") or device.get("ip") or "",
        "vendor": kv.get("Manufacturer") or device.get("vendor_display") or "",
        "model": kv.get("Model") or device.get("model") or "",
        "serial": device.get("serial") or "",
        "version": version or "Windows",
        "cpu": cpu, "memory": memory, "disk": disk_best, "disk_root": None,
        "disk_rows": disk_rows, "temp": None,
        "uptime": uptime_text, "uptime_seconds": uptime_seconds,
        "failed_services": len([x for x in _lines(service_text) if x.strip()])
        if service_text.strip() else None,
        "log_errors": len([x for x in _lines(log_text) if x.strip()])
        if log_text.strip() else None,
        "backups": len([x for x in _lines(backup_text) if x.strip()])
        if backup_text.strip() else None,
    }


# ---------------------------------------------------------------- 记录
def build_records(raw: dict, os_type: str, device: dict, commands: list) -> dict:
    """解析结果 → 平台写库用的记录（设备 / 巡检 / 监控 / 指标 / 告警）。"""
    info = parse_windows(raw, device) if os_type == "windows" else parse_linux(raw, device)
    cpu, memory, disk, temp = info["cpu"], info["memory"], info["disk"], info["temp"]
    issues, alerts = [], []

    def flag(level, metric, content, value=None, issue=True):
        alerts.append({"source": "monitor", "severity": level, "metric": metric,
                       "dedupe_key": metric, "content": content, "value": value})
        if issue:
            issues.append(content)

    if cpu is not None:
        if cpu >= 90:
            flag("2", "cpu_high", "CPU 使用率 %.0f%% 过高" % cpu, cpu)
        elif cpu >= 80:
            flag("4", "cpu_high", "CPU 使用率 %.0f%% 偏高" % cpu, cpu)
    if memory is not None:
        if memory >= 90:
            flag("2", "memory_high", "内存使用率 %.0f%% 过高" % memory, memory)
        elif memory >= 80:
            flag("4", "memory_high", "内存使用率 %.0f%% 偏高" % memory, memory)
    if disk is not None:
        if disk >= 90:
            flag("2", "disk_high", "磁盘使用率 %.0f%% 过高" % disk, disk)
        elif disk >= 85:
            flag("4", "disk_high", "磁盘使用率 %.0f%% 偏高" % disk, disk)
    if temp is not None:
        if temp >= 60:
            flag("2", "temp_high", "机箱温度 %.1f℃ 过高" % temp, temp)
        elif temp >= 50:
            flag("4", "temp_high", "机箱温度 %.1f℃ 偏高" % temp, temp)
    if info.get("failed_services"):
        flag("4", "service_failed",
             "%d 个系统服务未处于运行状态" % info["failed_services"],
             info["failed_services"])
    if info.get("log_errors") is not None and info["log_errors"] >= 20:
        flag("4", "log_errors", "系统日志近 20 条中错误事件 %d 条" % info["log_errors"],
             info["log_errors"], issue=False)

    metrics = []
    if disk is not None:
        metrics.append({"metric": "disk", "label": "磁盘使用率",
                        "value": disk, "unit": "%"})
    if info.get("disk_root") is not None:
        metrics.append({"metric": "disk_root", "label": "根分区使用率",
                        "value": info["disk_root"], "unit": "%"})
    if temp is not None:
        metrics.append({"metric": "temp", "label": "机箱温度",
                        "value": temp, "unit": "℃"})
    if info.get("failed_services") is not None:
        metrics.append({"metric": "failed_services", "label": "未运行服务",
                        "value": info["failed_services"], "unit": "个"})

    return {
        "kind": "server",
        "os_type": os_type,
        "device": {
            "name": info["hostname"] or device.get("name") or device.get("ip") or "",
            "vendor": "windows" if os_type == "windows" else "linux",
            "vendor_display": info["vendor"] or ("Windows Server" if os_type == "windows"
                                                 else "Linux 服务器"),
            "model": info["model"], "serial": info["serial"], "version": info["version"],
        },
        "inspection": {
            "device_cpu": cpu, "device_memory": memory,
            "stp_state": "", "stp_mode": "", "stp_forward": None, "stp_blocked": None,
            "error_ports": 0, "error_total": 0,
            "healthy": not issues, "issues": "；".join(issues),
        },
        "monitor": {"sysname": info["hostname"], "serial": info["serial"],
                    "version": info["version"], "cpu": cpu, "memory": memory},
        "metrics": metrics, "alerts": alerts,
        "commands": commands,
        "uptime": info["uptime"], "uptime_seconds": info["uptime_seconds"],
        "ports": [],
        "os_name": info["os_name"], "backups": info.get("backups"),
    }


# ---------------------------------------------------------------- 采集执行
def _run(client, command: str, timeout: float) -> tuple:
    """执行一条只读命令，返回 (输出, 退出码)。stdout/stderr 都收，便于看到报错原因。"""
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    try:
        out = stdout.read().decode("utf-8", "replace")
    except Exception:                                       # noqa: BLE001
        out = ""
    try:
        err = stderr.read().decode("utf-8", "replace")
    except Exception:                                       # noqa: BLE001
        err = ""
    try:
        code = stdout.channel.recv_exit_status()
    except Exception:                                       # noqa: BLE001
        code = 0
    text = (out or "").strip()
    if not text and err:
        text = err.strip()
    return text, code


def detect_os(client, timeout: float, forced: str = "") -> str:
    """Linux / Windows 探测：先 uname -s，失败再问 Windows 版本。"""
    forced = (forced or "").strip().lower()
    if forced in ("linux", "windows"):
        return forced
    try:
        text, code = _run(client, "uname -s", min(timeout, 8))
        if code == 0 and text and any(word in text.lower()
                                      for word in ("linux", "darwin", "freebsd")):
            return "linux"
    except Exception:                                       # noqa: BLE001
        pass
    try:
        text, _code = _run(client, "cmd /c ver", min(timeout, 8))
        if "windows" in (text or "").lower():
            return "windows"
    except Exception:                                       # noqa: BLE001
        pass
    return "linux"                     # 默认按 Linux 试；失败原因会原样落进回显与采集日志


def collect_from_client(client, device: dict, timeout: float = 25.0,
                        os_type: str = "", backup_path: str = "",
                        backup_paths: dict | None = None) -> dict:
    """在已建立的 SSH 连接上采集一台服务器（连接的关闭由调用方负责）。

    backup_paths 形如 {"linux": "/var/backups", "windows": "C:\\Backup"}，
    留空则用 DEFAULT_BACKUP_PATH。
    """
    started = time.time()
    os_type = detect_os(client, timeout, os_type)
    buckets = WINDOWS_BUCKETS if os_type == "windows" else LINUX_BUCKETS
    path = ((backup_paths or {}).get(os_type) or backup_path
            or DEFAULT_BACKUP_PATH.get(os_type, ""))

    outputs = {}
    commands = []
    for key, steps in buckets:
        for _label, command, tag in steps:
            actual = command.replace("<PATH>", path.replace("'", "''")) \
                if "<PATH>" in command else command
            if os_type == "windows":
                actual = 'powershell -NoProfile -NonInteractive -Command "%s"' % actual
            try:
                text, _code = _run(client, actual, timeout)
            except Exception as exc:                        # noqa: BLE001
                text = "命令执行失败：%s: %s" % (type(exc).__name__, exc)
            outputs.setdefault(key, {})[tag] = text
            commands.append(actual)

    echo = build_echo(buckets, outputs, os_type)
    records = build_records(outputs, os_type, device, commands)
    records["raw"] = echo              # 写库留档、报告截图都用这份带提示符的分桶回显
    records["echo"] = echo
    records["duration_ms"] = int((time.time() - started) * 1000)
    return records


