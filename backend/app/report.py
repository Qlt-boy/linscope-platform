# -*- coding: utf-8 -*-
"""报表导出：Excel（openpyxl）与 CSV。

一份报表一个工作簿，多张 Sheet（总览 / 明细 / 汇总），表头样式与页面表格同一套
配色（主色 #1A73E8），列宽自适应，冻结首行。导出后在 `exports` 表留一条归档记录，
「巡检报告中心」的归档列表直接读它。
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import normalize as nz
from . import service

BRAND = "1A73E8"
HEAD_FILL = PatternFill("solid", fgColor=BRAND)
HEAD_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=13, color="202124")
THIN = Side(style="thin", color="E5E7EB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _sheet(workbook, title, headers, rows, widths=None):
    ws = workbook.create_sheet(title=title[:31])
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(vertical="center", horizontal="left")
        cell.border = BORDER
    ws.row_dimensions[1].height = 22
    for row in rows:
        ws.append(["" if v is None else v for v in row])
    for idx, _ in enumerate(headers, start=1):
        letter = get_column_letter(idx)
        if widths and idx - 1 < len(widths):
            ws.column_dimensions[letter].width = widths[idx - 1]
        else:
            longest = max([len(str(headers[idx - 1]))] +
                          [len(str(r[idx - 1])) for r in rows if idx - 1 < len(r)] or [10])
            ws.column_dimensions[letter].width = min(48, max(12, longest + 4))
    ws.freeze_panes = "A2"
    return ws


def _cover(workbook, title, meta_rows):
    ws = workbook.active
    ws.title = "报告封面"
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=16, color="202124")
    ws.append([])
    for key, value in meta_rows:
        ws.append([key, value])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11, color="5F6368")
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 64
    return ws


def _meta(kind_label: str, period: str, source_label: str) -> list:
    values = service.settings()
    return [
        ("报告名称", kind_label),
        ("组织单位", values.get("org_name") or ""),
        ("统计区间", period),
        ("数据来源", source_label),
        ("生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("生成平台", values.get("site_name") or "林鉴知微平台 | LinScopePlatform"),
        ("健康度口径", "100 − 巡检异常扣分 − CPU/内存阈值扣分（80%/90%） − 接口错包 − 离线"),
    ]


def _source_label(source: str) -> str:
    return "本平台自带采集（SSH 只读）"


def build_devices(params: dict):
    """设备台账导出。"""
    data, source, _ = service.devices_view()
    period = {"period": "全部在册设备"}
    headers = ["序号", "设备名称", "设备类型", "品牌型号", "IP 地址", "序列号",
               "系统版本", "所在分组", "地区", "在线状态", "健康度", "健康状态",
               "最近巡检", "资产编号", "责任人", "用途", "备注"]
    rows = []
    for idx, dev in enumerate(data, start=1):
        rows.append([
            idx, dev["name"], dev["type_label"], dev["model"] or "—", dev["ip"],
            dev["serial"] or "—", dev["version"] or "—", dev["group"] or "—",
            dev["region"] or "—", "在线" if dev["online"] else "离线",
            dev["health_score"] if dev["health_score"] is not None else "—",
            dev["health_label"], dev["last_inspected_text"] or "尚未巡检",
            dev["ledger"].get("asset_no") or "", dev["ledger"].get("owner") or "",
            dev["ledger"].get("usage") or "", dev["ledger"].get("note") or "",
        ])
    wb = Workbook()
    _cover(wb, "设备台账清单", _meta("设备台账清单", "全部在册设备", _source_label(source)))
    _sheet(wb, "设备台账", headers, rows)
    summary = [["设备类型", "数量"]] + _counts([[d["type_label"]] for d in data])
    _sheet(wb, "分类汇总", ["设备类型", "数量"], summary[1:])
    return "设备台账清单", wb, len(rows)


def _counts(pairs):
    tally: dict = {}
    for item in pairs:
        key = item[0]
        tally[key] = tally.get(key, 0) + 1
    return [[k, v] for k, v in sorted(tally.items(), key=lambda kv: -kv[1])]


def build_inspection(params: dict):
    """巡检记录明细导出（含 CPU / 内存 / 异常项）。"""
    hours = int(params.get("hours") or 24 * 30)
    data = service.inspection_rows(hours=hours, limit=5000)
    headers = ["序号", "巡检时间", "设备名称", "IP 地址", "设备类型", "CPU %",
               "内存 %", "巡检结论", "健康度", "异常记录", "批次 run_id"]
    rows = []
    for idx, rec in enumerate(data["rows"], start=1):
        rows.append([idx, rec["time"], rec["device"], rec["device_ip"], rec["type"],
                     rec["cpu"] if rec["cpu"] is not None else "",
                     rec["memory"] if rec["memory"] is not None else "",
                     "正常" if rec["healthy"] else "异常",
                     rec["score"] if rec["score"] is not None else "",
                     rec["issues"], rec.get("run_id") or ""])
    wb = Workbook()
    _cover(wb, "网络设备巡检报告", _meta("网络设备巡检报告",
                                     service._period_label(hours),
                                     _source_label(data["source"])))
    _sheet(wb, "巡检明细", headers, rows)

    grouped: dict = {}
    for rec in data["rows"]:
        key = rec["device"] or rec["device_ip"]
        bucket = grouped.setdefault(key, {"type": rec["type"], "count": 0,
                                          "scores": [], "bad": 0,
                                          "last": rec["time"]})
        bucket["count"] += 1
        if rec["score"] is not None:
            bucket["scores"].append(rec["score"])
        if not rec["healthy"]:
            bucket["bad"] += 1
        if rec["time"] > bucket["last"]:
            bucket["last"] = rec["time"]
    summary_rows = []
    for name, bucket in sorted(grouped.items()):
        avg = round(sum(bucket["scores"]) / len(bucket["scores"]), 1) if bucket["scores"] else ""
        summary_rows.append([name, bucket["type"], bucket["count"], avg,
                             bucket["bad"], bucket["last"]])
    _sheet(wb, "按设备汇总", ["设备", "类型", "巡检次数", "平均健康度", "异常次数",
                             "最近巡检"], summary_rows)
    return "网络设备巡检报告", wb, len(rows)


def build_health_report(kind: str, params: dict):
    """服务器 / 交换机健康性检查报告（单台设备或整类设备遍历）。"""
    hours = int(params.get("hours") or 24 * 7)
    devices, source, _ = service.devices_view()
    wanted = kind if kind in ("server", "switch", "security") else "switch"
    target = params.get("device")
    pool = [d for d in devices if d["group_kind"] == wanted]
    if target:
        pool = [d for d in pool if str(d["id"]) == str(target) or d["ip"] == target]
    if not pool:
        pool = []
    label = {"server": "服务器健康性检查报告", "switch": "内网交换机健康性检查报告", "security": "安全设备健康性检查报告"}.get(wanted, "健康性检查报告")
    wb = Workbook()
    _cover(wb, label, _meta(label, service._period_label(hours), _source_label(source)))
    rows = []
    detail_rows = []
    for dev in pool:
        page = service.health_page(wanted, dev["id"])
        if not page.get("device"):
            continue
        checks = page.get("checks") or []
        abnormal = len([c for c in checks if c.get("tone") in ("danger", "warning")])
        rows.append([dev["name"], dev["ip"], dev["type_label"], dev["model"] or "—",
                     dev["version"] or "—", "在线" if dev["online"] else "离线",
                     dev["health_score"] if dev["health_score"] is not None else "—",
                     dev["health_label"], len(checks), abnormal,
                     dev["last_inspected_text"] or "尚未巡检"])
        for check in checks:
            detail_rows.append([dev["name"], dev["ip"], check.get("item"),
                                check.get("cmd") or "", check.get("result"),
                                check.get("purpose") or check.get("note") or ""])
    _sheet(wb, "设备健康汇总",
           ["设备名称", "IP 地址", "设备类型", "型号", "版本", "在线状态", "健康度",
            "健康状态", "检查项", "异常项", "最近巡检"], rows)
    _sheet(wb, "检查项明细",
           ["设备名称", "IP 地址", "检查项", "检查方式 / 命令", "检查结果", "说明"], detail_rows)
    return label, wb, len(rows)


def build_alerts(params: dict):
    hours = int(params.get("hours") or 24 * 30)
    data = service.alert_board(hours=hours, limit=5000)
    headers = ["序号", "触发时间", "告警内容", "来源", "级别", "状态", "设备", "IP 地址",
               "指标", "取值"]
    rows = []
    for idx, card in enumerate(data["cards"], start=1):
        rows.append([idx, card["time"], card["title"], card["source"],
                     card["severity_label"], card["status"], card["device"],
                     card["device_ip"], card["metric"],
                     card["value"] if card["value"] is not None else ""])
    wb = Workbook()
    _cover(wb, "告警与异常处置报告",
           _meta("告警与异常处置报告", service._period_label(hours),
                 _source_label(data["source"])))
    _sheet(wb, "告警清单", headers, rows)
    group_rows = []
    for item in data.get("groups") or []:
        group_rows.append([item.get("severity_label") or "", item.get("device") or "",
                           item.get("device_ip") or "", item.get("metric") or "",
                           item.get("title") or "", item.get("count") or 0,
                           item.get("resource_count") or 0, item.get("first_time") or "",
                           item.get("last_time") or "", "未恢复" if item.get("open")
                           else (item.get("status") or "")])
    _sheet(wb, "聚合告警",
           ["级别", "设备", "IP 地址", "指标族", "聚合内容", "次数", "影响对象",
            "首次出现", "最近出现", "状态"], group_rows)
    _sheet(wb, "收敛统计", ["指标", "取值"], [
        ["原始告警数", data.get("raw_total") or 0],
        ["聚合后分组", data.get("group_total") or 0],
        ["已收敛告警", data.get("collapsed") or 0],
        ["收敛比例", "%s%%" % (data.get("collapse_rate") or 0)],
    ])
    sev_rows = [[k, v] for k, v in data["by_severity"].items()]
    _sheet(wb, "按级别汇总", ["级别", "数量"], sev_rows)
    stat = data["by_status"]
    _sheet(wb, "按状态汇总", ["状态", "数量"], [[k, v] for k, v in stat.items()])
    return "告警与异常处置报告", wb, len(rows)


def build_backup(params: dict):
    data = service.backup_overview()
    headers = ["序号", "备份文件", "设备 IP", "大小", "修改时间"]
    rows = []
    for idx, item in enumerate(data["files"], start=1):
        rows.append([idx, item["name"], item["device_ip"], item["size_text"],
                     item["time_text"]])
    wb = Workbook()
    _cover(wb, "配置备份完整性报告",
           _meta("配置备份完整性报告", "全部备份文件", _source_label(data["source"])))
    _sheet(wb, "备份清单", headers, rows)
    _sheet(wb, "覆盖率汇总", ["指标", "取值"], [
        ["备份文件总数", data["file_count"]],
        ["备份总容量", data["total_size_text"]],
        ["设备台账总数", data["devices_total"]],
        ["已备份设备数", data["devices_covered"]],
        ["最近备份时间", data["newest"] or "—"],
    ])
    return "配置备份完整性报告", wb, len(rows)


def build_overview(params: dict):
    days = int(params.get("days") or 7)
    data = service.overview(days)
    wb = Workbook()
    _cover(wb, "巡检总览报告", _meta("巡检总览报告", data["period"]["label"],
                                 _source_label(data["source"])))
    kpi_rows = [[k["label"], k["value"], k["unit"], k["note"]] for k in data["kpis"]]
    _sheet(wb, "KPI 指标", ["指标", "数值", "单位", "说明"], kpi_rows)
    trend = data["trend"]
    trend_rows = []
    for idx, label in enumerate(trend["labels"]):
        row = [label]
        for series in trend["series"]:
            value = series["values"][idx]
            row.append(value if value is not None else "")
        trend_rows.append(row)
    _sheet(wb, "健康度趋势", ["日期"] + [s["name"] for s in trend["series"]], trend_rows)
    res_rows = [[r["name"], r["type"], r["cpu"], r["memory"], r["time"]]
                for r in data["resources"]["devices"]]
    _sheet(wb, "设备资源使用率", ["设备", "类型", "CPU %", "内存 %", "采集时间"], res_rows)
    recent = [[r["target"], r["type"], r["time"], r["owner"], r["score"], r["status"]]
              for r in data["recent_inspections"]]
    _sheet(wb, "最近巡检记录", ["巡检对象", "设备类型", "巡检时间", "巡检人", "健康度",
                             "状态"], recent)
    abnormal = [[a["device"], a["ip"], a["reason"]] for a in data["abnormal"]]
    _sheet(wb, "异常检查项", ["设备", "IP 地址", "异常说明"], abnormal)
    return "巡检总览报告", wb, len(recent)


def build_audit(params: dict):
    """操作审计导出（来自本平台 auth_events 操作留痕）。"""
    hours = int(params.get("hours") or 24 * 7)
    data = service.audit_rows(hours=hours, limit=500)
    headers = ["序号", "时间", "操作人", "动作", "对象类型", "对象", "详情", "来源 IP"]
    rows = [[i, r["time"], r["username"], r["action_label"], r["object_type"],
             r["object_name"], r["detail"], r["ip"]]
            for i, r in enumerate(data.get("rows") or [], start=1)]
    wb = Workbook()
    _cover(wb, "操作审计记录",
           _meta("操作审计记录", service._period_label(hours),
                 _source_label(service.status().get("source", ""))))
    _sheet(wb, "审计记录", headers, rows)
    if not data.get("available"):
        _sheet(wb, "取数说明", ["项", "说明"],
               [["审计不可用", data.get("error") or "本平台审计未返回数据"],
                ["提示", "操作审计只对管理员令牌开放，请用管理员账号签发令牌"]])
    else:
        _sheet(wb, "按操作人汇总",
               ["操作人", "操作次数", "最近活动", "动作分布"],
               [[u["username"], u["count"], u["last_text"], u["actions_text"]]
                for u in data.get("by_user") or []])
    return "操作审计记录", wb, len(rows)


def build_ledger(params: dict):
    """台账导出：设备身份字段 + 台账补充字段。"""
    data = service.ledger_export()
    headers = ["IP 地址", "设备名称", "设备类型", "品牌型号", "厂商", "分组", "地区",
               "在线状态", "健康度", "健康状态", "资产编号", "责任人", "设备用途",
               "设备地点", "维保到期", "类型纠正", "备注", "台账更新时间"]
    rows = [[r["ip"], r["name"], r["type_label"], r["model"], r["vendor"], r["group"],
             r["region"], r["online"], r["health_score"], r["health_label"],
             r["asset_no"], r["owner"], r["usage"], r["location"],
             r["warranty_until"], r["kind_override"], r["note"], r["updated_at"]]
            for r in data["rows"]]
    wb = Workbook()
    _cover(wb, "设备台账（含台账补充）",
           _meta("设备台账（含台账补充）", "全部在册设备", _source_label(data["source"])))
    _sheet(wb, "设备台账", headers, rows)
    filled = len([r for r in data["rows"] if r["owner"] or r["asset_no"]])
    _sheet(wb, "台账完整度", ["指标", "取值"], [
        ["设备总数", data["total"]],
        ["已填责任人/资产编号", filled],
        ["未填台账字段", data["total"] - filled],
        ["说明", "未填字段只影响本平台台账视图，不影响采集"],
    ])
    return "设备台账（含台账补充）", wb, len(rows)


BUILDERS = {
    "devices": build_devices,
    "inspection": build_inspection,
    "server": lambda params: build_health_report("server", params),
    "switch": lambda params: build_health_report("switch", params),
    "security": lambda params: build_health_report("security", params),
    "alerts": build_alerts,
    "backup": build_backup,
    "overview": build_overview,
    "audit": build_audit,
    "ledger": build_ledger,
}


def to_excel(kind: str, params: dict) -> tuple[str, bytes, int]:
    builder = BUILDERS.get(kind) or build_overview
    label, workbook, row_count = builder(params)
    stream = io.BytesIO()
    workbook.save(stream)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return "%s-%s.xlsx" % (label, stamp), stream.getvalue(), row_count


def to_csv(kind: str, params: dict) -> tuple[str, bytes, int]:
    """CSV 导出：跳过封面，把其余工作表**依次拼接**（段与段之间空一行 + `## 工作表名`）。

    只用第一张表会丢掉汇总信息，而 CSV 又没法承载多表，所以这里按段落拼起来，
    带 UTF-8 BOM，Excel 直接双击不乱码。
    """
    label, workbook, row_count = BUILDERS.get(kind, build_overview)(params)
    sheets = [ws for ws in workbook.worksheets[1:]] or [workbook.active]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    # 先写一段报告信息：CSV 常被转发出去，打开时得知道这是哪份报告、什么时候生成的
    cover = workbook.worksheets[0] if workbook.worksheets else None
    if cover is not None:
        writer.writerow(["## 报告信息"])
        for meta_row in cover.iter_rows(values_only=True):
            if meta_row and any(cell not in (None, "") for cell in meta_row):
                writer.writerow(["" if v is None else v for v in meta_row])
        writer.writerow([])
    for index, sheet in enumerate(sheets):
        if index:
            writer.writerow([])
        writer.writerow(["## " + sheet.title])
        for row in sheet.iter_rows(values_only=True):
            writer.writerow(["" if v is None else v for v in row])
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return "%s-%s.csv" % (label, stamp), buffer.getvalue().encode("utf-8-sig"), row_count

