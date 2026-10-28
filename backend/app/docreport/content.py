# -*- coding: utf-8 -*-
"""版式报告的内容装配：把平台已有的数据拼成一份可交付的健康性检查报告。

口径（与平台其它页面一致，不额外造数）：

* 设备台账 / 巡检 / 监控 / 告警 / 备份 —— 来自 service（本平台自带采集写入的本地库）；
* 命令回显 —— 来自本平台自带采集留档的 collect_logs.raw_excerpt（按命令分段的原始回显），
  逐条命令渲染成终端风格截图；没有留档就如实写"未采集"，绝不用样例回显充数；
* 现场目视类项目（指示灯 / 风扇 / 电源 / 温湿度）平台采不到，一律留成
  "现场确认：正常 □异常"，由维护工程师现场勾选——与参考样例的表格写法一致。
"""
from __future__ import annotations

from datetime import datetime

from .. import normalize as nz
from .. import service
from ..store import get_store
from . import imaging
from .blocks import (Report, bullets, h1, h2, h3, h4, img, note, p, pagebreak,
                     spacer, table)

KINDS = ("server", "switch", "security")

TITLES = {
    "server": "服务器健康性检查报告",
    "switch": "内网交换机健康性检查报告",
    "security": "安全设备健康性检查报告",
}

#: 交换机：命令回显截图的顺序与中文名（key 与采集留档里的分段标记一致）
SWITCH_COMMANDS = [
    ("version", "display version", "软件版本与运行时长"),
    ("serial", "display device manuinfo", "设备序列号 / 单板信息"),
    ("cpu", "display cpu-usage", "CPU 利用率"),
    ("memory", "display memory-usage", "内存利用率"),
    ("interfaces", "display interface", "接口状态与错包统计"),
    ("stp", "display stp brief", "生成树（STP）状态"),
    ("lldp", "display lldp neighbor", "LLDP 邻居"),
    ("alarm", "display alarm", "设备告警"),
    ("config", "display current-configuration", "当前配置（配置备份）"),
]

#: 服务器：命令回显截图（回显来自平台的检查通道留档，没有就写未采集）
SERVER_COMMANDS = [
    ("os", "uname -srm / os-release / DMI", "操作系统与版本"),
    ("cpu", "top -bn1 / Win32_Processor", "CPU 平均利用率"),
    ("memory", "free -m / Win32_OperatingSystem", "内存平均利用率"),
    ("disk", "df -hT / Win32_LogicalDisk", "磁盘使用情况"),
    ("net", "ip -br addr / Get-NetIPAddress", "网络配置与连通性"),
    ("service", "systemctl --failed / Get-Service", "应用系统运行状态"),
    ("log", "journalctl -p err / Get-WinEvent", "系统日志检查"),
    ("temp", "thermal_zone / 温度传感器", "机箱温度"),
    ("backup", "ls -lt <备份目录> / Get-ChildItem", "配置 / 数据备份"),
]

SECURITY_COMMANDS = [
    ("version", "display version", "系统 / 软件版本"),
    ("serial", "display device manuinfo", "设备序列号 / 单板信息"),
    ("cpu", "display cpu-usage", "CPU 利用率"),
    ("memory", "display memory-usage", "内存利用率"),
    ("interfaces", "display interface", "接口状态与错包统计"),
    ("alarm", "display alarm", "安全设备告警"),
    ("config", "display current-configuration", "当前配置（配置备份）"),
]
PROMPTS = {"switch": "<HUAWEI>", "security": "<HUAWEI>", "server": "root@host:~#"}

#: 机房环境巡检（与现场样例一致的判定口径）
ENV_ROWS = [
    ("工作温度", "10℃～ 35℃（41℉～ 95℉）间正常"),
    ("存储温度", "-40℃～+65℃（-40℉～ 149℉）"),
    ("温度变化率", "15℃/h（59℉/h）"),
    ("工作湿度", "8% RH ～ 90% RH（无冷凝）"),
    ("存储湿度", "5% RH ～ 95% RH（无冷凝）"),
    ("工作海拔高度", "≤3000m"),
    ("电源", "交流供电：输入电压范围 100V AC ～ 240V AC，50/60Hz；"
             "直流供电：标称 -48VDC，电压波动范围 –38.4V ～ –57.6V DC"),
]

#: 交换机健康性检查评估项（口径照搬现场样例，便于与既有交付物对齐）
SWITCH_CRITERIA = [
    ("软件版本", "display version",
     "版本是否是正式版本，是否符合软件规范，保证无未知的系统崩溃情况出现。", "正式版本",
     "软件版本"),
    ("CPU 利用率", "display cpu-usage", "检查当前系统的 CPU 利用率",
     "（1）CPU 利用率高于 50% 认为不正常，需做好记录；"
     "（2）如发现当前 CPU 利用率高于 50%，需记录占用过高（超过 10%）的项目。",
     "CPU 利用率"),
    ("内存利用率", "display memory-usage", "检查当前系统的内存利用率",
     "内存占用情况正常；Memory Using Percentage 超过 60% 时需要关注。", "内存利用率"),
    ("日志信息", "display logbuffer / display trapbuffer",
     "检查系统日志是否开启，是否存在大量重复的、异常的日志信息。", "不存在异常信息", None),
    ("硬件检查", "display fan / display temperature all / display power",
     "检查单板风扇、电源运行状态及温度情况。",
     "风扇状态 Status 为 normal；当前温度不高于 45℃；电源 state 项为 supply。", None),
    ("接口检查", "display interface brief", "检查端口运行状态是否正常",
     "PHY Up / Protocol Up 为正常；PHY administratively down / Protocol Down 为正常；"
     "PHY Down / Protocol Down 为未用端口；PHY Up / Protocol Down 为不正常。",
     "接口错包统计"),
    ("单板运行状态", "display device", "关注单板在位信息及状态信息是否正常。",
     "Online = Present；Power = PowerOn；Register = Registered；Status = Normal。", None),
    ("FTP 网络服务端口", "display ftp-server", "确认设备未开放无用的文件服务端口。",
     "不使用的 FTP 网络服务端口要关闭。", None),
    ("端口所属 VLAN", "display port vlan", "确认端口归属清晰。", "各端口所属 VLAN 需明确。", None),
    ("VLAN 信息", "display vlan", "核对 VLAN 划分。", "VLAN 划分与规划一致。", None),
    ("告警信息", "display alarm", "检查设备当前是否有未恢复告警。",
     "无告警信息（display alarm 回显为空）。", "告警与事件"),
    ("IP 路由协议", "display ip routing-table", "查看各路由协议所有路由的概要信息。",
     "显示路由协议、下一跳、优先级信息。", None),
    ("配置备份", "display current-configuration", "确认存在可回滚的配置备份。",
     "存在最近一次配置备份，且备份时间在巡检周期内。", "配置备份"),
]

#: 服务器健康性检查评估项
SECURITY_CRITERIA = [
    ("系统 / 软件版本", "display version", "确认系统版本、补丁与运行时长。", "正式版本且运行时长稳定。", "软件版本"),
    ("CPU 利用率", "display cpu-usage", "检查安全设备控制平面 CPU 水位。", "低于 80%；持续高于 80% 需定位策略或流量异常。", "CPU 利用率"),
    ("内存利用率", "display memory-usage", "检查会话表、策略等资源占用。", "低于 80%；持续增长需排查会话泄漏。", "内存利用率"),
    ("接口错包统计", "display interface", "检查业务口与管理口链路质量。", "无持续增长的 CRC / Errors。", "接口错包统计"),
    ("安全策略基线", "display security-policy / show policy", "检查策略最小化、冗余策略与危险放通。", "符合安全基线，无临时长期放通策略。", "安全策略基线"),
    ("HA / 双机热备", "display hrp state / show high-availability", "检查主备状态、心跳链路与配置同步。", "主备状态正常，配置同步一致。", "HA / 双机热备"),
    ("特征库 / 规则库", "display update status / show signature", "检查 IPS / 防病毒 / URL 特征库版本。", "特征库在有效更新周期内。", "特征库 / 规则库"),
    ("会话与并发", "display firewall session table / show session", "检查会话数、新建速率与资源余量。", "低于设备规格阈值并符合业务基线。", "会话与并发"),
    ("告警与事件", "display logbuffer / display alarm", "检查近期安全事件与设备告警。", "无未处置的严重告警。", "告警与事件"),
    ("配置备份", "display current-configuration", "确认存在可回滚的安全配置备份。", "近期已有成功配置备份。", "配置备份"),
]
SERVER_CRITERIA = [
    ("主机在线状态", "采集通道 / 带外管理", "确认被监控服务器在线可管理。",
     "在线可管理，最近在线时间在巡检周期内。", "主机在线状态"),
    ("操作系统 / 版本", "systeminfo / uname -a", "确认操作系统版本在厂商服务期内。",
     "受支持的操作系统版本，未停止安全更新。", "操作系统 / 版本"),
    ("CPU 平均利用率", "性能监视器 / CPU 采样", "检查服务器 CPU 平均利用率。",
     "平均利用率低于 80%，无持续满载。", "CPU 平均利用率"),
    ("内存平均利用率", "性能监视器 / 内存采样", "检查服务器内存平均利用率。",
     "平均利用率低于 80%，无持续换页。", "内存平均利用率"),
    ("磁盘使用情况", "df -h / 磁盘管理", "检查系统盘与数据盘空间占用。",
     "使用率低于 90%，保留可用空间。", "磁盘使用情况"),
    ("机箱温度", "带外管理 / 温度传感器", "检查机箱进风与关键部件温度。",
     "当前温度不高于 45℃。", "机箱温度"),
    ("硬件指示灯", "现场查看前面板 / 电源 / 磁盘指示灯",
     "确认前面板、电源、磁盘指示灯状态。", "各指示灯为绿色常亮，无红色告警灯。", None),
    ("系统风扇运转", "现场确认 / 带外管理", "确认系统风扇运转正常。",
     "风扇运转正常、无异常噪音。", None),
    ("网络连接", "ping / ipconfig", "检查业务网络连通性。",
     "业务网段互通，无持续丢包。", None),
    ("日志检查", "journalctl / 事件查看器", "检查系统日志是否存在异常。",
     "无 ERROR 级异常日志，无异常重启记录。", None),
    ("系统漏洞", "漏洞扫描 / 补丁清单", "检查系统补丁与高危漏洞。",
     "无未处置的高危漏洞。", None),
    ("系统防病毒", "杀毒软件控制台", "检查防病毒软件运行状态。",
     "病毒库为最新，实时防护已开启。", None),
    ("告警检查", "本平台告警中心", "检查是否有未恢复告警。",
     "无未恢复告警。", "告警检查"),
    ("配置 / 数据备份", "备份任务", "检查配置与数据备份。",
     "存在最近一次可用备份。", "配置 / 数据备份"),
    ("采集时点", "采集 / 巡检任务记录", "确认最近一次巡检与采集的时间。",
     "巡检时间在检查周期内。", "巡检时点"),
    ("健康度评分", "平台健康度口径", "按平台健康度口径给出综合评分。",
     "评分不低于 85 分（低于 60 分为异常）。", "健康度评分"),
]

#: 维护建议模板（与现场样例一致的兜底条目）
GENERAL_ADVICE = [
    "定期进行设备硬件及软件的巡检，巡检结果归档留存，形成可追溯的运维记录。",
    "定期对设备进行例行检查和测试，并记录检查结果，定期备份数据与设备配置。",
    "对巡检中发现的异常项建立台账，明确整改责任人与完成时间，整改后复跑一次检查确认恢复。",
    "关注设备资源利用率的变化趋势，在达到告警阈值之前提前扩容或调整业务分布。",
    "设备软件版本保持与厂商推荐版本一致，升级前做好配置与数据备份。",
]


# ---------------------------------------------------------------- 小工具
def _now() -> datetime:
    return datetime.now()


def _cn_month(moment: datetime) -> str:
    return "%d年%d月" % (moment.year, moment.month)


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _zone(dev: dict) -> str:
    text = " ".join([str(dev.get("name") or ""), str(dev.get("group") or ""),
                     str(dev.get("region") or ""),
                     str((dev.get("ledger") or {}).get("usage") or "")]).lower()
    for key in ("外网", "internet", "edge", "出口", "边界", "dmz", "公网"):
        if key in text:
            return "外网"
    return "内网"


def parse_echo(raw_excerpt: str) -> dict:
    """把采集日志里的回显摘要拆成 {命令 key: 回显正文}。

    留档格式是 "──── <key> ────" 分段（见 app/collect/runner.raw_excerpt）。
    """
    echo: dict = {}
    current = None
    buffer: list = []
    for line in (raw_excerpt or "").replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped.startswith("────") and stripped.endswith("────") and len(stripped) > 10:
            if current:
                echo[current] = "\n".join(buffer).strip()
            current = stripped.strip("─").strip()
            buffer = []
            continue
        if current:
            buffer.append(line)
    if current:
        echo[current] = "\n".join(buffer).strip()
    return echo


def _check_of(checks, item_name):
    for check in checks or []:
        if check.get("item") == item_name:
            return check
    return None


# ---------------------------------------------------------------- 设备数据
def _device_bundle(kind: str, dev: dict) -> dict:
    """把一台设备在报告里要用到的数据一次取齐。"""
    store = get_store()
    ip = dev.get("ip")
    page = service.health_page(kind, dev.get("id")) or {}
    inspections = sorted(
        [r for r in store.inspections()
         if r.get("device_ip") == ip or str(r.get("device_id")) == str(dev.get("id"))],
        key=lambda r: str(r.get("inspected_at") or ""), reverse=True)
    alerts = sorted([a for a in store.alerts() if a.get("device_ip") == ip],
                    key=lambda a: str(a.get("triggered_at") or ""), reverse=True)
    backups = [b for b in store.backup_rows() if b.get("device_ip") == ip]
    logs = store.collect_logs(ip=ip, limit=10, with_raw=True)
    ok_logs = [row for row in logs
               if row.get("ok") and (row.get("raw_excerpt") or "").strip()]
    latest = ok_logs[0] if ok_logs else None
    echo = parse_echo(latest.get("raw_excerpt") if latest else "")
    return {
        "dev": dev, "page": page, "inspections": inspections,
        "insp": inspections[0] if inspections else None,
        "alerts": alerts, "backups": backups,
        "log": latest, "echo": echo,
        "log_time": (latest or {}).get("created_at") or "",
    }


def _cpu_mem(bundle: dict):
    dev = bundle.get("dev") or {}
    insp = bundle.get("insp") or {}
    cpu = _num(dev.get("cpu"))
    mem = _num(dev.get("memory"))
    if cpu is None:
        cpu = _num(insp.get("cpu"))
    if mem is None:
        mem = _num(insp.get("memory"))
    return cpu, mem


def _severity_label(alert: dict) -> str:
    """告警级别统一走平台口径（数字级别 → 紧急/严重/警告/通知/信息）。"""
    raw = alert.get("severity")
    try:
        return nz.severity_view(raw)[1]
    except Exception:                                       # noqa: BLE001
        return str(alert.get("severity_label") or raw or "未分级")


def _unresolved(alerts) -> list:
    return [a for a in (alerts or [])
            if (a.get("status") or "") not in ("resolved", "closed")]


def _criteria_for(kind: str):
    if kind == "server":
        return SERVER_CRITERIA
    if kind == "security":
        return SECURITY_CRITERIA
    return SWITCH_CRITERIA


def _commands_for(kind: str):
    if kind == "server":
        return SERVER_COMMANDS
    if kind == "security":
        return SECURITY_COMMANDS
    return SWITCH_COMMANDS

# ---------------------------------------------------------------- 封面 / 概述 / 环境
def _cover_meta(kind: str, params: dict, org: str, site: str) -> dict:
    now = _now()
    customer = params.get("customer") or "XXX公司"
    return {
        "title": "%s网络信息系统维护巡检以及健康性检查报告" % customer,
        "signatures": ["维护工程师签字：", "客户参与人员签字："],
        "org": org,
        "date": _cn_month(now),
        "project": params.get("project") or "%s%d年网络信息系统维护项目" % (customer, now.year),
        "subtitle": "——%s" % TITLES[kind],
        "subtitle_page": [
            params.get("project") or "%s%d年网络信息系统维护项目" % (customer, now.year),
            "——%s" % TITLES[kind],
            org,
            _cn_month(now),
        ],
        "customer": customer,
        "footer": site,
    }


def _env_block(kind: str) -> list:
    rows = []
    for index, (item, standard) in enumerate(ENV_ROWS, start=1):
        rows.append([index, item, "正常", standard])
    if kind == "server":
        rows.append([len(rows) + 1, "清洁状态", "清洁", "机房无可见积尘，设备进风口无遮挡"])
    return [
        h1("二、设备所在机房环境巡检"),
        p("检查机房环境主要包括机房内部的空调、供电设备、温湿度与清洁状况。"
          "下列技术指标项由现场目视或机房环境监控确认，结果栏为现场填写口径。"),
        table(["序号", "技术指标项", "结果", "说明"], rows,
              widths=[8, 18, 12, 62], align=["c", "l", "c", "l"], zebra=True),
    ]


def _device_list_block(kind: str, devices: list) -> list:
    if kind == "server":
        return [
            h1("三、服务器设备列表"),
            p("下表列出本期纳入检查范围的服务器主机。品牌型号与操作系统由设备台账回填，"
              "台账里没有的字段显示为 —，不做推测。"),
            table(["序号", "设备名称（主机名）", "品牌型号及配置", "操作系统", "IP 地址"],
                  _host_table(devices), widths=[8, 26, 30, 20, 16],
                  align=["c", "l", "l", "l", "l"], zebra=True),
        ]
    if kind == "security":
        rows = [[i, d.get("name") or "", d.get("type_label") or "", d.get("model") or "—",
                 d.get("ip") or "", d.get("version") or "—", d.get("group") or "—"]
                for i, d in enumerate(devices, start=1)]
        return [
            h1("三、安全设备列表"),
            p("下表列出本期纳入检查范围的防火墙、WAF、IPS/IDS、VPN 等安全设备。"),
            table(["序号", "设备名称", "设备类型", "型号", "IP 地址", "软件版本", "分组"],
                  rows, widths=[7, 18, 14, 17, 12, 20, 12],
                  align=["c", "l", "l", "l", "l", "l", "l"], zebra=True),
        ]
    inner = _site_table_switch(devices, "内网")
    outer = _site_table_switch(devices, "外网")
    return [
        h1("三、信息中心内外网设备列表"),
        h2("3.1 内网设备"),
        table(["局点", "设备角色", "设备名称", "IP 地址", "设备型号", "设备软件版本", "设备序列号"],
              inner, widths=[11, 13, 17, 12, 16, 16, 15],
              align=["l", "l", "l", "l", "l", "l", "l"], zebra=True),
        h2("3.2 外网设备"),
        table(["局点", "设备角色", "设备名称", "IP 地址", "设备型号", "设备软件版本", "设备序列号"],
              outer, widths=[11, 13, 17, 12, 16, 16, 15],
              align=["l", "l", "l", "l", "l", "l", "l"], zebra=True),
    ]


def _criteria_block(kind: str) -> list:
    criteria = _criteria_for(kind)
    rows = [[item, cmd, purpose, standard] for item, cmd, purpose, standard, _key in criteria]
    return [
        h1("四、%s健康性检查评估项" % ("服务器" if kind == "server" else ("安全设备" if kind == "security" else "交换机"))),
        p("下表为本期健康性检查的评估口径：检查项、检查方式命令、检查目的与评估标准。"
          "后续「检查详细情况」中的结果，均按下表的评估标准判定。"),
        table(["检查项", "检查方式命令", "检查目的", "评估标准"], rows,
              widths=[14, 20, 30, 36], align=["l", "l", "l", "l"], zebra=True),
    ]


# ---------------------------------------------------------------- 现场巡检表
def _onsite_switch(bundle: dict, period: str, generated: str) -> tuple:
    """交换机现场巡检表：分组 + 首列纵向合并。"""
    dev = bundle["dev"]
    insp = bundle.get("insp") or {}
    ledger = dev.get("ledger") or {}
    cpu, mem = _cpu_mem(bundle)
    err_total = _num(insp.get("error_total"))
    err_ports = _num(insp.get("error_ports"))
    stp = (insp.get("stp_state") or "").lower()
    backups = bundle.get("backups") or []
    echo = bundle.get("echo") or {}
    confirm = "现场确认：正常 □异常"

    def none_yet(what):
        return "现场确认：正常 □异常（%s）" % what

    alarm_body = (echo.get("alarm") or "").strip()
    alarm_lines = [line for line in alarm_body.split("\n")
                   if line.strip().startswith("0x")]

    groups = [
        ("设备基本信息", [
            ("设备地点", "机房 / 机柜位置",
             ledger.get("location") or dev.get("region") or dev.get("group") or "—"),
            ("设备名称 / 型号", "台账名称与硬件型号",
             "%s / %s" % (dev.get("name") or "—", dev.get("model") or "—")),
            ("设备在网状态", "采集通道可达性",
             "在线可管理" if dev.get("online")
             else "离线（最近在线 %s）" % (nz.fmt_time(dev.get("last_online_at")) or "未记录")),
        ]),
        ("设备面板检查", [
            ("面板指示灯", "PWR1-PWR3 / RUN-ALM / Mode：绿色常亮为正常", confirm),
            ("端口指示灯", "Port stat：Link Up 端口指示灯亮，收发包时闪烁", confirm),
        ]),
        ("设备软硬件检查", [
            ("设备温度", "display environment，标准 -10℃ ～ 72℃",
             none_yet("需 display environment 回显")),
            ("设备业务板", "display device，Status = Normal",
             none_yet("需 display device 回显")),
            ("设备电源", "display power，state = supply / Normal",
             none_yet("需 display power 回显")),
            ("设备风扇", "display fan，Status = normal",
             none_yet("需 display fan 回显")),
            ("CPU 占用率", "display cpu-usage，标准 0 ～ 50%",
             ("%.0f%%（%s）" % (cpu, "正常" if cpu < 50 else "高于 50%，需记录"))
             if cpu is not None else "未采集"),
            ("内存占用率", "display memory-usage，标准 0 ～ 60%",
             ("%.0f%%（%s）" % (mem, "正常" if mem < 60 else "高于 60%，需关注"))
             if mem is not None else "未采集"),
        ]),
        ("设备配置业务连通性检查", [
            ("端口统计数据", "display interface，异常报文无增长",
             ("正常：%d 个接口有错包，累计 %d 个" % (err_ports or 0, err_total or 0))
             if err_total else ("正常：未发现错包" if insp else "未采集")),
            ("生成树协议", "display stp，已启用且转发口正常",
             {"enabled": "正常：STP 已启用（转发 %s / 阻塞 %s）" % (
                 insp.get("stp_forward"), insp.get("stp_blocked")),
              "disabled": "异常：STP 已禁用"}.get(stp, "未采集")),
            ("网络基本运行状态", "采集通道可达性",
             "正常：采集通道可达" if dev.get("online") else "异常：采集通道不可达"),
            ("系统时间与时钟服务器同步", "display clock",
             none_yet("需 display clock 回显")),
            ("端口描述", "display current-configuration，端口描述与拓扑一致",
             ("正常：已归档 %d 份配置" % len(backups)) if backups
             else "未采集：尚无配置备份"),
            ("日志告警", "display logbuffer summary / display alarm",
             ("未采集" if not echo else
              ("异常：%d 条告警" % len(alarm_lines)) if alarm_lines
              else "正常：本次回显无告警")),
            ("设备配置保存", "display saved-configuration",
             ("正常：%d 份备份" % len(backups)) if backups
             else "未采集：尚无配置备份"),
        ]),
    ]
    rows, spans = [], []
    for title, items in groups:
        start = len(rows)
        for item, expect, result in items:
            rows.append([title, item, expect, result])
        spans.append((start, 0, len(rows) - 1, 0))

    unresolved = _unresolved(bundle.get("alerts"))
    issues = (insp.get("issues") or "").strip()
    summary = ("设备运行正常，未发现影响业务的异常项。"
               if not issues and not unresolved
               else "；".join([x for x in [issues,
                                          ("存在 %d 条未恢复告警，需要处置" % len(unresolved))
                                          if unresolved else ""] if x]))
    index = len(rows)
    rows.append(["巡检总结", summary, "", ""])
    spans.append((index, 1, index, 3))
    rows.append(["巡检时间", "巡检周期：%s" % period,
                 "本次巡检：%s" % (nz.fmt_time(insp.get("inspected_at")) or "尚未巡检"),
                 "报告生成：%s" % generated])
    return rows, spans


def _onsite_server(bundle: dict, period: str, generated: str) -> tuple:
    dev = bundle["dev"]
    insp = bundle.get("insp") or {}
    ledger = dev.get("ledger") or {}
    checks = (bundle.get("page") or {}).get("checks") or []
    cpu, mem = _cpu_mem(bundle)
    disk = None
    temp = None
    disk_note = str((_check_of(checks, "磁盘使用情况") or {}).get("note") or "")
    if "%" in disk_note:
        disk = _num(disk_note.split("%")[0].replace("使用率", "").strip())
    temp_note = str((_check_of(checks, "机箱温度") or {}).get("note") or "")
    if "℃" in temp_note:
        temp = _num(temp_note.split("℃")[0].replace("当前", "").strip())
    backups = bundle.get("backups") or []
    unresolved = _unresolved(bundle.get("alerts"))
    confirm = "现场确认：正常 □异常"

    groups = [
        ("主机基础信息", [
            ("主机名 / IP", "设备台账",
             "%s / %s" % (dev.get("name") or "—", dev.get("ip") or "—")),
            ("品牌型号", "设备台账",
             "%s %s" % (dev.get("vendor") or "", dev.get("model") or "—")),
            ("操作系统", "systeminfo / uname -a", dev.get("version") or "—"),
            ("机房位置", "台账 / 现场",
             ledger.get("location") or dev.get("region") or dev.get("group") or "—"),
            ("在网状态", "采集通道可达性",
             "在线可管理" if dev.get("online")
             else "离线（最近在线 %s）" % (nz.fmt_time(dev.get("last_online_at")) or "未记录")),
        ]),
        ("硬件状态检查", [
            ("前面板指示灯", "现场目视：绿色常亮、无红色告警灯", confirm),
            ("电源指示灯", "现场目视：双电源均正常供电", confirm),
            ("磁盘指示灯", "现场目视：磁盘活动灯闪烁、无故障灯", confirm),
            ("系统风扇运转", "现场确认：运转正常、无异常噪音", confirm),
        ]),
        ("运行状态检查", [
            ("CPU 平均利用率", "性能采样，标准低于 80%",
             ("%.0f%%（%s）" % (cpu, "正常" if cpu < 80 else "已达告警阈值"))
             if cpu is not None else "未采集"),
            ("内存平均利用率", "性能采样，标准低于 80%",
             ("%.0f%%（%s）" % (mem, "正常" if mem < 80 else "已达告警阈值"))
             if mem is not None else "未采集"),
            ("磁盘使用情况", "df -h / 磁盘管理，标准低于 90%",
             "%.0f%%" % disk if disk is not None else "未采集"),
            ("机箱温度", "带外管理 / 温度传感器，标准不高于 45℃",
             "%.1f℃" % temp if temp is not None else "未采集"),
        ]),
        ("系统与安全检查", [
            ("操作系统版本支持", "厂商服务期", "已核实" if dev.get("version") else "未采集"),
            ("系统日志", "journalctl / 事件查看器", confirm),
            ("系统漏洞", "漏洞扫描 / 补丁清单", "现场确认：有 □无"),
            ("系统防病毒", "杀毒软件控制台", confirm),
        ]),
        ("备份与告警", [
            ("配置 / 数据备份", "备份任务",
             ("已归档 %d 份" % len(backups)) if backups else "未采集：尚无备份记录"),
            ("未恢复告警", "本平台告警中心",
             ("%d 条" % len(unresolved)) if bundle.get("alerts") else "0 条（无告警记录）"),
        ]),
    ]
    rows, spans = [], []
    for title, items in groups:
        start = len(rows)
        for item, expect, result in items:
            rows.append([title, item, expect, result])
        spans.append((start, 0, len(rows) - 1, 0))

    summary = ("服务器硬件工作情况正常，操作系统常规性能正常，文件系统使用情况正常。"
               if not unresolved
               else "存在 %d 条未恢复告警，需要处置后复检。" % len(unresolved))
    index = len(rows)
    rows.append(["巡检总结", summary, "", ""])
    spans.append((index, 1, index, 3))
    rows.append(["巡检时间", "巡检周期：%s" % period,
                 "本次巡检：%s" % (nz.fmt_time(insp.get("inspected_at")) or "尚未巡检"),
                 "报告生成：%s" % generated])
    return rows, spans


def _onsite_table(kind: str, bundle: dict, period: str, generated: str) -> list:
    builder = _onsite_server if kind == "server" else _onsite_switch
    rows, spans = builder(bundle, period, generated)
    return [table(["检查类别", "检查项 / 巡检项目", "检查说明 / 判定标准", "检查结果"],
                  rows, widths=[13, 19, 40, 28], align=["c", "l", "l", "l"], spans=spans)]


def _standard_table(kind: str, checks) -> list:
    """健康性检查标准表：评估标准 + 检查结果。"""
    criteria = _criteria_for(kind)
    rows = []
    for item, _cmd, purpose, standard, key in criteria:
        if key:
            check = _check_of(checks, key)
            if check:
                result = check.get("result") or "未采集"
                note_text = check.get("purpose") or check.get("note") or ""
                if item in ("CPU 利用率", "内存利用率", "CPU 平均利用率",
                            "内存平均利用率", "磁盘使用情况", "机箱温度"):
                    result = "%s（%s）" % (result, note_text) if note_text else result
            else:
                result = "现场确认：正常 □异常"
        else:
            result = "现场确认：正常 □异常"
        rows.append([item, purpose, standard, result])
    return [table(["检查项", "检查目的", "评估标准", "检查结果"], rows,
                  widths=[15, 28, 39, 18], align=["l", "l", "l", "l"], zebra=True)]


def _detail_table(kind: str, checks) -> list:
    """检查详细情况表：检查项 / 检查方式命令 / 检查目的 / 检查结果。

    检查项来自平台健康检查页；服务器侧的检查项没有带命令字段，这里按评估项表
    补上对应的检查方式命令（对照不上就留 —，不编命令）。
    """
    criteria = _criteria_for(kind)
    cmd_of = {item: cmd for item, cmd, _purpose, _standard, _key in criteria}
    rows = [[c.get("item") or "—",
             c.get("cmd") or cmd_of.get(c.get("item") or "") or "—",
             c.get("purpose") or c.get("note") or "—", c.get("result") or "未采集"]
            for c in (checks or [])]
    if not rows:
        rows = [["—", "—", "本平台尚未采集到该设备的检查明细", "未采集"]]
    return [table(["检查项", "检查方式命令", "检查目的 / 说明", "检查结果"], rows,
                  widths=[18, 22, 42, 18], align=["l", "l", "l", "l"], zebra=True)]


# ---------------------------------------------------------------- 命令回显截图
def _figure(fig: dict, text: str) -> str:
    fig["n"] = int(fig.get("n") or 0) + 1
    return "图 %d %s" % (fig["n"], text)


def _command_blocks(kind: str, bundle: dict, prefix: str, fig: dict) -> list:
    echo = bundle.get("echo") or {}
    commands = _commands_for(kind)
    blocks = [h3("%s 命令回显截图" % prefix)]
    if not echo:
        log = bundle.get("log")
        reason = ("该设备在平台内没有成功的采集留档（最近一次采集：%s）"
                  % (log or {}).get("reason", "") if log
                  else "该设备在本平台没有采集留档")
        blocks.append(note("暂无命令回显截图：%s。命令回显来自本平台自带采集落库的原始回显，"
                           "到「采集任务」页对该设备补采一次后重新导出本报告即可。" % reason))
        return blocks
    index = 0
    missing = []
    for key, cmd, label in commands:
        body = (echo.get(key) or "").strip()
        if not body:
            missing.append(cmd)
            continue
        index += 1
        blocks.append(h4("%s.%d %s —— %s" % (prefix, index, cmd, label)))
        # 服务器采集的回显正文里已经带 "$ 命令" / "PS> 命令" 行，标题栏显示检查项即可；
        # 交换机回显没有命令行，才补一行提示符。
        blocks.append(img(
            imaging.terminal_png(cmd, "" if kind == "server" else cmd, body,
                                 prompt=PROMPTS.get(kind, "<HUAWEI>"), max_columns=88),
            width_cm=15.6,
            caption=_figure(fig, "%s 命令回显截图（采集留档 %s）"
                            % (cmd, bundle.get("log_time") or "时间未记录"))))
    if missing:
        blocks.append(note("本期未留档回显的命令：%s（该命令未抓取，或本次回显为空）。"
                           % "、".join(missing)))
    return blocks


# ---------------------------------------------------------------- 单台设备数据分析
def _analysis_blocks(kind: str, bundle: dict, prefix: str, fig: dict) -> list:
    dev = bundle["dev"]
    insp = bundle.get("insp") or {}
    checks = (bundle.get("page") or {}).get("checks") or []
    cpu, mem = _cpu_mem(bundle)
    alerts = bundle.get("alerts") or []
    unresolved = _unresolved(alerts)
    backups = bundle.get("backups") or []
    history = list(reversed(bundle.get("inspections") or []))[-20:]

    blocks = [h3("%s 数据分析" % prefix)]

    # 1) 资源利用率
    rows = [("CPU 利用率", cpu, "阈值：80% 告警 / 90% 严重"),
            ("内存利用率", mem, "阈值：80% 告警 / 90% 严重")]
    blocks.append(img(imaging.util_bars("资源利用率（最近一次巡检）", rows),
                      width_cm=15.6, caption=_figure(fig, "资源利用率（%s）" % (dev.get("name") or ""))))

    # 2) 走势
    if len(history) >= 2:
        labels = [str(row.get("inspected_at") or "")[5:16] for row in history]
        cpu_series = [_num(row.get("cpu")) for row in history]
        mem_series = [_num(row.get("memory")) for row in history]
        if any(v is not None for v in cpu_series + mem_series):
            blocks.append(img(
                imaging.line_chart("CPU / 内存利用率走势（近 %d 次巡检）" % len(history),
                                   labels, [("CPU", cpu_series, imaging.BRAND),
                                            ("内存", mem_series, imaging.ORANGE)],
                                   unit="%", y_max=100),
                width_cm=15.6, caption=_figure(fig, "资源利用率走势（%s）" % (dev.get("name") or ""))))

    # 3) 结论文字
    lines = []
    name = dev.get("name") or dev.get("ip") or "该设备"
    score = dev.get("health_score")
    if score is not None:
        lines.append("%s 当前健康度 %s 分（%s）。健康度口径：100 分减去巡检异常扣分、"
                     "CPU/内存阈值扣分（80%%/90%%）、接口错包扣分与离线扣分。"
                     % (name, score, dev.get("health_label") or "—"))
    if cpu is not None:
        position = ("低于 50% 的关注阈值，资源水位健康" if cpu < 50 else
                    "已高于 50% 的关注阈值，建议核对是否有业务突发或环路" if cpu < 80 else
                    "已达 80% 告警阈值，需要立即定位高占用进程")
        trend = ""
        cpu_series = [_num(row.get("cpu")) for row in history]
        values = [v for v in cpu_series if v is not None]
        if len(values) >= 3:
            trend = ("；窗口内最高 %.0f%% / 最低 %.0f%%" % (max(values), min(values)))
        lines.append("CPU 最近一次巡检为 %.0f%%，%s%s。" % (cpu, position, trend))
    if mem is not None:
        position = ("低于 60% 的关注阈值" if mem < 60 else
                    "已达到 60% 的关注阈值，建议排查内存泄漏或业务增长" if mem < 80 else
                    "已达 80% 告警阈值，存在内存耗尽风险")
        lines.append("内存最近一次巡检为 %.0f%%，%s。" % (mem, position))

    if kind != "server":
        err_total = _num(insp.get("error_total"))
        err_ports = _num(insp.get("error_ports"))
        if err_total is None:
            lines.append("接口错包统计未采集到，无法判断链路质量，建议在采集设置里放开"
                         "「display interface」并复采一次。")
        elif err_total == 0:
            lines.append("接口错包统计为 0，链路质量正常，无 CRC/Errors 增长。")
        else:
            lines.append("接口错包：%d 个接口存在错误包，累计 %d 个，"
                         "建议逐口核对光模块与网线，排除链路劣化。"
                         % (err_ports or 0, err_total))
        stp = (insp.get("stp_state") or "").lower()
        if stp == "enabled":
            lines.append("生成树运行正常：转发口 %s 个、阻塞口 %s 个，"
                         "冗余链路收敛符合预期。"
                         % (insp.get("stp_forward"), insp.get("stp_blocked")))
        elif stp == "disabled":
            lines.append("生成树处于禁用状态，存在环路风险，建议在业务允许的窗口内恢复 STP。")
    else:
        for item in ("磁盘使用情况", "机箱温度"):
            check = _check_of(checks, item)
            if check:
                lines.append("%s：%s —— %s。" % (item, check.get("result") or "未采集",
                                                 check.get("purpose") or check.get("note") or ""))

    if not dev.get("online"):
        lines.append("%s 当前不可达，最近在线 %s，请优先排查链路与电源。"
                     % (name, nz.fmt_time(dev.get("last_online_at")) or "未记录"))
    if alerts:
        by_sev: dict = {}
        for alert in alerts:
            label = _severity_label(alert)
            by_sev[label] = by_sev.get(label, 0) + 1
        lines.append("告警：近 90 天共 %d 条（%s），其中未恢复 %d 条。"
                     % (len(alerts),
                        "、".join("%s %d 条" % (k, v) for k, v in by_sev.items()),
                        len(unresolved)))
    else:
        lines.append("告警：近 90 天没有该设备的告警记录。")
    lines.append("配置备份：%s。"
                 % (("已归档 %d 份，最近一份为 %s" % (len(backups), backups[0].get("name") or "—"))
                    if backups else "尚无备份，建议立即补一次配置备份"))
    blocks.append(p("\n".join(lines)))
    return blocks


def _advice_blocks(kind: str, bundle: dict, prefix: str) -> list:
    dev = bundle["dev"]
    page = bundle.get("page") or {}
    advice = list(page.get("advice") or [])
    if not advice:
        advice = ["按现有巡检周期保持例行检查。", "定期备份设备配置，保留可回滚的版本快照。"]
    return [h3("%s 问题与处置建议" % prefix),
            bullets(["%d. %s" % (i, text) for i, text in enumerate(advice, start=1)])]


# ---------------------------------------------------------------- 汇总分析
def _summary_blocks(kind: str, bundles: list, fig: dict) -> list:
    blocks = [h1("六、数据分析汇总")]
    total = len(bundles)
    if not total:
        blocks.append(note("本期没有纳入检查范围的设备。"))
        return blocks

    # 健康度分布
    buckets = [("优秀（≥90）", 0, imaging.GREEN), ("良好（75-89）", 0, imaging.BRAND_SOFT),
               ("一般（60-74）", 0, imaging.ORANGE), ("异常（<60）", 0, imaging.RED)]
    tally = [0, 0, 0, 0]
    unknown = 0
    for bundle in bundles:
        score = bundle["dev"].get("health_score")
        if score is None:
            unknown += 1
        elif score >= 90:
            tally[0] += 1
        elif score >= 75:
            tally[1] += 1
        elif score >= 60:
            tally[2] += 1
        else:
            tally[3] += 1
    parts = [(name, count, color)
             for (name, _c, color), count in zip(buckets, tally) if count]
    if unknown:
        parts.append(("未评（无巡检数据）", unknown, imaging.GRAY))
    blocks.append(img(imaging.donut_chart("设备健康度分布", parts, center_label="设备总数"),
                      width_cm=15.6, caption=_figure(fig, "设备健康度分布")))

    # 各设备健康度 / CPU / 内存
    names = [(b["dev"].get("name") or b["dev"].get("ip") or "—") for b in bundles]
    scores = [b["dev"].get("health_score") for b in bundles]
    cpus = [_cpu_mem(b)[0] for b in bundles]
    mems = [_cpu_mem(b)[1] for b in bundles]
    blocks.append(img(imaging.bar_chart(
        "各设备健康度", names, scores, unit="", width=1180, height=420,
        show_value=True, y_max=100,
        colors=[imaging.score_color(v) for v in scores]),
        width_cm=15.6, caption=_figure(fig, "各设备健康度对比")))
    blocks.append(img(imaging.bar_chart("各设备 CPU 利用率", names, cpus, unit="%",
                                        warn=80, danger=90, threshold=80,
                                        threshold_label="告警阈值 80%"),
                      width_cm=15.6, caption=_figure(fig, "各设备 CPU 利用率")))
    blocks.append(img(imaging.bar_chart("各设备内存利用率", names, mems, unit="%",
                                        warn=80, danger=90, threshold=80,
                                        threshold_label="告警阈值 80%"),
                      width_cm=15.6, caption=_figure(fig, "各设备内存利用率")))

    # 巡检结论
    ok = bad = none = 0
    for bundle in bundles:
        insp = bundle.get("insp")
        if not insp:
            none += 1
        elif insp.get("healthy"):
            ok += 1
        else:
            bad += 1
    conclusion = []
    if ok:
        conclusion.append(("巡检判定正常", ok, imaging.GREEN))
    if bad:
        conclusion.append(("巡检判定异常", bad, imaging.RED))
    if none:
        conclusion.append(("尚无巡检记录", none, imaging.GRAY))
    blocks.append(img(imaging.donut_chart("巡检结论分布", conclusion, center_label="设备总数"),
                      width_cm=15.6, caption=_figure(fig, "巡检结论分布")))

    # 告警
    by_sev: dict = {}
    for bundle in bundles:
        for alert in bundle.get("alerts") or []:
            label = _severity_label(alert)
            by_sev[label] = by_sev.get(label, 0) + 1
    if by_sev:
        colors = {"紧急": imaging.RED, "告警": imaging.RED, "严重": imaging.RED,
                  "错误": imaging.ORANGE, "警告": imaging.ORANGE,
                  "通知": imaging.BRAND_SOFT, "提示": imaging.BRAND_SOFT,
                  "信息": imaging.GRAY, "调试": imaging.GRAY}
        seg = [(name, count, colors.get(name, imaging.BRAND)) for name, count in by_sev.items()]
        blocks.append(img(imaging.donut_chart("告警级别分布（近 90 天）", seg,
                                              center_label="告警总数", unit="条"),
                          width_cm=15.6, caption=_figure(fig, "告警级别分布")))
    else:
        blocks.append(note("近 90 天没有与本期设备相关的告警记录。"))

    # 配置备份
    with_backup = len([b for b in bundles if b.get("backups")])
    backup_parts = [("已有配置备份", with_backup, imaging.GREEN)]
    if total - with_backup:
        backup_parts.append(("尚无配置备份", total - with_backup, imaging.RED))
    blocks.append(img(imaging.donut_chart("配置备份覆盖率", backup_parts, center_label="设备总数"),
                      width_cm=15.6, caption=_figure(fig, "配置备份覆盖率")))

    # 文字分析
    text = []
    text.append("本期共检查 %d 台设备。健康度分布：%s%s。"
                % (total,
                   "、".join("%s %d 台" % (name.split("（")[0], count)
                             for name, count, _c in parts) or "无",
                   "；另有 %d 台尚无巡检数据，暂不评分" % unknown if unknown else ""))
    avg = [s for s in scores if s is not None]
    if avg:
        text.append("平均健康度 %.1f 分，最高 %d 分、最低 %d 分。"
                    % (sum(avg) / len(avg), max(avg), min(avg)))
    cpu_values = [v for v in cpus if v is not None]
    mem_values = [v for v in mems if v is not None]
    if cpu_values:
        hot = [names[i] for i, v in enumerate(cpus) if v is not None and v >= 80]
        text.append("CPU 利用率均值 %.1f%%，最高 %.0f%%（%s）%s。"
                    % (sum(cpu_values) / len(cpu_values), max(cpu_values),
                       names[cpus.index(max(cpu_values))],
                       "；%s 已达告警阈值，建议优先处置" % "、".join(hot) if hot else ""))
    if mem_values:
        text.append("内存利用率均值 %.1f%%，最高 %.0f%%（%s）。"
                    % (sum(mem_values) / len(mem_values), max(mem_values),
                       names[mems.index(max(mem_values))]))
    text.append("巡检结论：正常 %d 台、异常 %d 台、尚无巡检记录 %d 台。"
                % (ok, bad, none))
    text.append("配置备份覆盖率 %d/%d（%.0f%%）%s。"
                % (with_backup, total, 100.0 * with_backup / total,
                   "，建议对未备份设备立即补采" if with_backup < total else ""))
    offline = [b["dev"].get("name") or b["dev"].get("ip")
               for b in bundles if not b["dev"].get("online")]
    if offline:
        text.append("当前不可达设备 %d 台（%s），需现场确认链路与电源状态。"
                    % (len(offline), "、".join(offline)))
    blocks.append(p("\n".join(text)))
    return blocks


def _advice_section(bundles: list) -> list:
    blocks = [h1("七、维护建议")]
    for index, text in enumerate(GENERAL_ADVICE, start=1):
        blocks.append(p("%d、%s" % (index, text)))
    per_device = []
    for bundle in bundles:
        for tip in (bundle.get("page") or {}).get("advice") or []:
            if tip not in per_device:
                per_device.append(tip)
    if per_device:
        blocks.append(h2("7.1 本期设备针对性建议"))
        for index, text in enumerate(per_device, start=1):
            blocks.append(p("%d、%s" % (index, text)))
    return blocks


def _appendix_block(kind: str, params: dict, meta: dict, bundles: list, source: str) -> list:
    from . import fonts as font_module
    info = font_module.describe()
    rows = [
        ["报告名称", TITLES[kind]],
        ["组织单位", meta.get("org") or ""],
        ["统计区间", meta.get("period") or ""],
        ["纳入设备", "%d 台" % len(bundles)],
        ["数据来源", service.source_label(source) or source],
        ["命令回显来源", "本平台自带采集留档（collect_logs.raw_excerpt，"
                        "按 display 命令分段）；未留档的命令在报告中如实注明"],
        ["现场确认项", "指示灯 / 风扇 / 电源 / 温湿度等平台采不到的项，"
                      "在表中留成「现场确认：正常 □异常」，由维护工程师现场勾选"],
        ["健康度口径", "100 − 巡检异常扣分 − CPU/内存阈值扣分（80%/90%）"
                      " − 接口错包 − 离线"],
        ["字体（PDF）", "%s / %s；截图等宽字体 %s"
                        % (info.get("cjk"), info.get("cjk_bold"), info.get("mono"))],
        ["生成时间", meta.get("generated") or ""],
        ["生成平台", meta.get("site") or ""],
    ]
    return [h1("八、数据来源与口径说明"),
            table(["项目", "说明"], rows, widths=[20, 80], align=["l", "l"], zebra=True)]


# ---------------------------------------------------------------- 主入口
def build(kind: str, params: dict) -> Report:
    """装配一份健康性检查报告（返回 Report，交给 Word / PDF 渲染器）。"""
    kind = (kind or "switch").lower()
    if kind not in KINDS:
        raise ValueError("版式报告只支持 %s" % "、".join(KINDS))
    params = dict(params or {})
    values = service.settings()
    org = params.get("org") or values.get("org_name") or "林鉴知微技术服务股份有限公司"
    site = values.get("site_name") or "林鉴知微平台 | LinScopePlatform"
    hours = int(params.get("hours") or 24 * 7)
    period = service._period_label(hours)

    devices, source, _info = service.devices_view()
    wanted = kind if kind in ("server", "switch", "security") else "switch"
    pool = [d for d in devices if d.get("group_kind") == wanted]
    target = params.get("device")
    targets = [part.strip() for part in str(target or "").replace(";", ",").split(",") if part.strip()]
    if targets:
        wanted_keys = set(targets)
        picked = [d for d in pool
                  if str(d.get("id")) in wanted_keys or str(d.get("ip")) in wanted_keys]
        if not picked:
            raise ValueError("未找到所选设备，请刷新设备清单后重试")
        pool = picked
    pool = sorted(pool, key=lambda d: (d.get("health_score") is None,
                                       d.get("health_score") or 0,
                                       str(d.get("name") or "")))

    bundles = [_device_bundle(kind, dev) for dev in pool]
    bundles = [b for b in bundles if b.get("page", {}).get("device")] or bundles

    now = _now()
    generated = now.strftime("%Y-%m-%d %H:%M:%S")
    cover = _cover_meta(kind, params, org, site)
    meta = {"org": org, "site": site, "period": period, "generated": generated,
            "cover": cover, "subtitle": cover["subtitle"],
            "project": cover["project"], "customer": cover["customer"],
            "footer": site, "device_count": len(bundles),
            "title": "%s%s" % (cover["customer"], TITLES[kind])}

    fig = {"n": 0}
    blocks = []
    blocks.extend(_env_block(kind))
    blocks.extend(_device_list_block(kind, [b["dev"] for b in bundles]))
    blocks.extend(_criteria_block(kind))

    section_five = ("具体服务器检查" if kind == "server"
                    else ("具体安全设备检查" if kind == "security"
                          else "内网交换机健康性检查情况"))
    blocks.append(h1("五、%s" % section_five))
    for index, bundle in enumerate(bundles, start=1):
        prefix = "5.%d" % index
        dev = bundle["dev"]
        role = (" / %s" % dev["type_label"]) if dev.get("type_label") else ""
        blocks.append(h2("%s %s%s" % (prefix, dev.get("name") or dev.get("ip") or "—", role)))
        blocks.append(h3("%s.1 现场巡检表" % prefix))
        blocks.extend(_onsite_table(kind, bundle, period, generated))
        blocks.append(h3("%s.2 健康性检查标准" % prefix))
        blocks.extend(_standard_table(kind, bundle.get("page", {}).get("checks")))
        blocks.append(h3("%s.3 检查详细情况" % prefix))
        blocks.extend(_detail_table(kind, bundle.get("page", {}).get("checks")))
        blocks.extend(_command_blocks(kind, bundle, "%s.4" % prefix, fig))
        blocks.extend(_analysis_blocks(kind, bundle, "%s.5" % prefix, fig))
        blocks.extend(_advice_blocks(kind, bundle, "%s.6" % prefix))
        blocks.append(pagebreak())

    blocks.extend(_summary_blocks(kind, bundles, fig))
    blocks.extend(_advice_section(bundles))
    blocks.extend(_appendix_block(kind, params, meta, bundles, source))
    return Report(TITLES[kind], meta, blocks)




# ---------------------------------------------------------------- 设备列表（表格数据）
def _site_table_switch(devices: list, zone: str) -> list:
    """交换机设备列表：按内网 / 外网分区（按分组、地区、用途里的关键词判区）。"""
    rows = []
    for dev in [d for d in devices if _zone(d) == zone]:
        ledger = dev.get("ledger") or {}
        rows.append([ledger.get("location") or dev.get("region") or dev.get("group") or "—",
                     dev.get("type_label") or "—", dev.get("name") or "—",
                     dev.get("ip") or "—", dev.get("model") or "—",
                     dev.get("version") or "—", dev.get("serial") or "—"])
    if not rows:
        rows.append(["—", "—", "本期无该区域在册设备", "—", "—", "—", "—"])
    return rows


def _host_table(devices: list) -> list:
    """服务器设备列表。"""
    rows = []
    for index, dev in enumerate(devices, start=1):
        rows.append([index, dev.get("name") or "—",
                     "%s / %s" % (dev.get("vendor_display") or dev.get("vendor") or "—",
                                  dev.get("model") or "—"),
                     dev.get("version") or "—", dev.get("ip") or "—"])
    if not rows:
        rows.append(["—", "台账中暂无服务器设备", "—", "—", "—"])
    return rows






