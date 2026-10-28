# -*- coding: utf-8 -*-
"""本地 SQLite：设备台账 + 采集结果 + 告警备份 + 导出归档。

本平台是**纯本地**的：设备、巡检、监控、指标、告警、配置备份全部由自带采集
（SSH 只读）写进这张库，页面与报表只读它，不依赖任何外部巡检平台。

1. **台账**：设备身份 + 资产编号 / 责任人 / 用途 / 维保到期等补充字段，按设备 IP 关联；
2. **采集结果**：inspection / monitor / metric / alert / backup，每次采集滚动写入；
3. **采集留痕**：collect_runs / collect_logs（执行过的命令 + 原始回显摘要）；
4. **导出归档**：每次导出的报表留一条记录，「巡检报告中心」的归档列表即来自这里。

只用标准库 sqlite3，每次操作开一个短连接（WAL 模式，读写互不阻塞）。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Iterable

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS devices (
    id             INTEGER PRIMARY KEY,
    ip             TEXT,
    name           TEXT,
    vendor         TEXT,
    vendor_display TEXT,
    model          TEXT,
    serial         TEXT,
    version        TEXT,
    role           TEXT,
    group_name     TEXT,
    region         TEXT,
    online         INTEGER DEFAULT 1,
    pending_collection INTEGER DEFAULT 0,
    port           INTEGER,
    last_online_at TEXT,
    updated_at     TEXT,
    payload        TEXT,
    synced_at      TEXT
);

CREATE TABLE IF NOT EXISTS inspections (
    id           INTEGER PRIMARY KEY,
    run_id       TEXT,
    device_id    INTEGER,
    device_name  TEXT,
    device_ip    TEXT,
    cpu          REAL,
    memory       REAL,
    stp_state    TEXT,
    stp_mode     TEXT,
    stp_forward  INTEGER,
    stp_blocked  INTEGER,
    error_ports  TEXT,
    error_total  INTEGER,
    healthy      INTEGER,
    issues       TEXT,
    error        TEXT,
    inspected_at TEXT,
    payload      TEXT,
    synced_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_insp_device ON inspections(device_id, inspected_at);

CREATE TABLE IF NOT EXISTS monitors (
    id           INTEGER PRIMARY KEY,
    device_id    INTEGER,
    device_name  TEXT,
    device_ip    TEXT,
    sysname      TEXT,
    serial       TEXT,
    version      TEXT,
    cpu          REAL,
    memory       REAL,
    ok           INTEGER,
    error        TEXT,
    collected_at TEXT,
    payload      TEXT,
    synced_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_mon_device ON monitors(device_id, collected_at);

CREATE TABLE IF NOT EXISTS metrics (
    id           INTEGER PRIMARY KEY,
    device_id    INTEGER,
    device_name  TEXT,
    device_ip    TEXT,
    metric       TEXT,
    label        TEXT,
    value        REAL,
    unit         TEXT,
    source       TEXT,
    collected_at TEXT,
    payload      TEXT,
    synced_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_metric ON metrics(device_id, metric, collected_at);

CREATE TABLE IF NOT EXISTS alerts (
    id             INTEGER PRIMARY KEY,
    source         TEXT,
    source_display TEXT,
    severity       TEXT,
    status         TEXT,
    device_ip      TEXT,
    device_name    TEXT,
    rule           TEXT,
    metric         TEXT,
    value          REAL,
    content        TEXT,
    triggered_at   TEXT,
    assignee       TEXT DEFAULT '',
    acknowledged_at TEXT DEFAULT '',
    acknowledged_by TEXT DEFAULT '',
    resolved_at    TEXT DEFAULT '',
    resolved_by    TEXT DEFAULT '',
    disposition_note TEXT DEFAULT '',
    payload        TEXT,
    synced_at      TEXT
);

CREATE TABLE IF NOT EXISTS backups (
    name      TEXT PRIMARY KEY,
    device_ip TEXT,
    size      INTEGER,
    mtime     TEXT,
    payload   TEXT,
    synced_at TEXT
);

CREATE TABLE IF NOT EXISTS ledger (
    device_ip      TEXT PRIMARY KEY,
    device_id      INTEGER,
    device_name    TEXT,
    asset_no       TEXT DEFAULT '',
    owner          TEXT DEFAULT '',
    usage          TEXT DEFAULT '',
    location       TEXT DEFAULT '',
    warranty_until TEXT DEFAULT '',
    kind_override  TEXT DEFAULT '',
    note           TEXT DEFAULT '',
    updated_at     TEXT
);

CREATE TABLE IF NOT EXISTS exports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT,
    fmt        TEXT,
    filename   TEXT,
    rows       INTEGER,
    params     TEXT,
    operator   TEXT,
    file_path  TEXT DEFAULT '',
    sha256     TEXT DEFAULT '',
    file_size  INTEGER DEFAULT 0,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    username              TEXT UNIQUE NOT NULL,
    display_name          TEXT DEFAULT '',
    role                  TEXT DEFAULT 'viewer',
    password_hash         TEXT DEFAULT '',
    enabled               INTEGER DEFAULT 1,
    note                  TEXT DEFAULT '',
    created_at            TEXT,
    updated_at            TEXT,
    last_login_at         TEXT,
    last_login_ip         TEXT,
    password_changed_at   TEXT
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash   TEXT PRIMARY KEY,
    user_id      INTEGER,
    username     TEXT,
    created_at   TEXT,
    expires_at   TEXT,
    last_seen_at TEXT,
    client_ip    TEXT,
    user_agent   TEXT DEFAULT '',
    revoked      INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions ON auth_sessions(username, revoked);

CREATE TABLE IF NOT EXISTS auth_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT,
    action      TEXT,
    detail      TEXT DEFAULT '',
    ip          TEXT DEFAULT '',
    actor       TEXT DEFAULT '',
    target_type TEXT DEFAULT '',
    result      TEXT DEFAULT '',
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_auth_events ON auth_events(created_at);
CREATE TABLE IF NOT EXISTS collect_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT,
    finished_at  TEXT,
    trigger      TEXT DEFAULT 'manual',
    operator     TEXT DEFAULT '',
    total        INTEGER DEFAULT 0,
    ok           INTEGER DEFAULT 0,
    failed       INTEGER DEFAULT 0,
    skipped      INTEGER DEFAULT 0,
    duration_ms  INTEGER DEFAULT 0,
    message      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS collect_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER,
    device_ip   TEXT,
    device_name TEXT,
    ok          INTEGER DEFAULT 0,
    reason      TEXT DEFAULT '',
    duration_ms INTEGER DEFAULT 0,
    commands    TEXT DEFAULT '',
    summary     TEXT DEFAULT '',
    raw_excerpt TEXT DEFAULT '',
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_collect_logs ON collect_logs(device_ip, id);

CREATE TABLE IF NOT EXISTS credentials (
    ip            TEXT PRIMARY KEY,
    device_name   TEXT DEFAULT '',
    port          INTEGER DEFAULT 22,
    username      TEXT DEFAULT '',
    auth          TEXT DEFAULT 'password',
    secret_enc    TEXT DEFAULT '',
    key_enc       TEXT DEFAULT '',
    key_pass_enc  TEXT DEFAULT '',
    host_key_type TEXT DEFAULT '',
    host_key_b64  TEXT DEFAULT '',
    host_key_fp   TEXT DEFAULT '',
    host_key_at   TEXT DEFAULT '',
    vendor        TEXT DEFAULT '',
    note          TEXT DEFAULT '',
    updated_at    TEXT,
    updated_by    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS remote_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_ip   TEXT,
    device_name TEXT,
    username    TEXT,
    operator    TEXT,
    client_ip   TEXT,
    started_at  TEXT,
    ended_at    TEXT,
    status      TEXT DEFAULT 'running',
    commands    INTEGER DEFAULT 0,
    blocked     INTEGER DEFAULT 0,
    error       TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_remote_sessions ON remote_sessions(device_ip, started_at);

CREATE TABLE IF NOT EXISTS remote_commands (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    device_ip  TEXT,
    command    TEXT,
    action     TEXT DEFAULT 'sent',
    reason     TEXT DEFAULT '',
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_remote_commands ON remote_commands(session_id, id);
"""


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_ID_LOCK = threading.Lock()
_ID_LAST = 0


def next_row_id() -> int:
    """给巡检/监控等写库记录生成**进程内唯一**主键。

    原来的 `int(time.time()*1000) % 10**9` 在并发采集时同一毫秒会撞主键，
    `INSERT OR REPLACE` 会把别的设备的记录顶掉（历史记录莫名少一条）。
    """
    global _ID_LAST
    with _ID_LOCK:
        value = int(time.time() * 1000) * 1000
        if value <= _ID_LAST:
            value = _ID_LAST + 1
        _ID_LAST = value
        return value


class Store:
    """本地库门面。所有方法都是「取设置 / 写快照 / 读快照 / 台账 / 导出记录」。"""

    def __init__(self, path=None):
        self.path = str(path or config.DB_PATH)

    # ------------------------------------------------------------ 基础
    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def init(self) -> None:
        self.path_dir()
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            # 老库缺列时补上（SQLite 不支持 IF NOT EXISTS ADD COLUMN）
            migrations = [
                ("collect_logs", "raw_excerpt TEXT DEFAULT ''"),
                ("auth_events", "actor TEXT DEFAULT ''"),
                ("auth_events", "target_type TEXT DEFAULT ''"),
                ("auth_events", "result TEXT DEFAULT ''"),
                ("alerts", "assignee TEXT DEFAULT ''"),
                ("alerts", "acknowledged_at TEXT DEFAULT ''"),
                ("alerts", "acknowledged_by TEXT DEFAULT ''"),
                ("alerts", "resolved_at TEXT DEFAULT ''"),
                ("alerts", "resolved_by TEXT DEFAULT ''"),
                ("alerts", "disposition_note TEXT DEFAULT ''"),
                ("collect_runs", "operator TEXT DEFAULT ''"),
                ("credentials", "host_key_type TEXT DEFAULT ''"),
                ("credentials", "host_key_b64 TEXT DEFAULT ''"),
                ("credentials", "host_key_fp TEXT DEFAULT ''"),
                ("credentials", "host_key_at TEXT DEFAULT ''"),
                ("exports", "file_path TEXT DEFAULT ''"),
                ("exports", "sha256 TEXT DEFAULT ''"),
                ("exports", "file_size INTEGER DEFAULT 0"),
                ("devices", "pending_collection INTEGER DEFAULT 0"),
            ]
            for table, ddl in migrations:
                try:
                    conn.execute("ALTER TABLE %s ADD COLUMN %s" % (table, ddl))
                except sqlite3.OperationalError:
                    pass
            # 旧库升级：从未成功巡检且当前离线/无管理 IP 的历史设备，归入待采集区。
            conn.execute(
                "UPDATE devices SET pending_collection=1"
                " WHERE pending_collection=0"
                " AND (online=0 OR ip LIKE 'noip-%')"
                " AND NOT EXISTS (SELECT 1 FROM inspections i WHERE i.device_ip=devices.ip)")

    def path_dir(self):
        import os
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    # ------------------------------------------------------------ 设置项
    def get_settings(self) -> dict:
        values = dict(config.default_settings())
        with self.connect() as conn:
            for row in conn.execute("SELECT key, value FROM settings"):
                values[row["key"]] = row["value"]
        return values

    def setting(self, key: str, default: str = "") -> str:
        return self.get_settings().get(key, default)

    def save_settings(self, values: dict) -> dict:
        stamp = now_iso()
        with self.connect() as conn:
            for key, value in values.items():
                if value is None:
                    continue
                conn.execute(
                    "INSERT INTO settings(key, value, updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                    "updated_at=excluded.updated_at",
                    (str(key), str(value), stamp))
        return self.get_settings()

    # ------------------------------------------------------------ 快照落库
    def _replace_rows(self, table: str, cols: list, rows: list) -> int:
        """按主键 REPLACE 写快照：cols 指定的列 + synced_at（写入时间）。"""
        cols = list(cols)
        sql = ("INSERT OR REPLACE INTO %s(%s,synced_at) VALUES(%s,?)"
               % (table, ",".join(cols), ",".join("?" * len(cols))))
        stamp = now_iso()
        with self.connect() as conn:
            for values in rows:
                conn.execute(sql, list(values) + [stamp])
        return len(rows)

    def save_devices(self, devices: list) -> int:
        cols = ["id", "ip", "name", "vendor", "vendor_display", "model",
                "serial", "version", "role", "group_name", "region", "online",
                "port", "last_online_at", "updated_at", "payload"]
        rows = [[
            dev.get("id"), dev.get("ip"), dev.get("name"), dev.get("vendor"),
            dev.get("vendor_display"), dev.get("model"), dev.get("serial"),
            dev.get("version"), dev.get("role"), dev.get("group"),
            dev.get("region"), 1 if dev.get("online") else 0, dev.get("port"),
            dev.get("last_online_at"), dev.get("updated_at"),
            json.dumps(dev, ensure_ascii=False)] for dev in devices]
        return self._replace_rows("devices", cols, rows)

    def save_inspections(self, rows_in: list) -> int:
        cols = ["id", "run_id", "device_id", "device_name", "device_ip", "cpu",
                "memory", "stp_state", "stp_mode", "stp_forward", "stp_blocked",
                "error_ports", "error_total", "healthy", "issues", "error",
                "inspected_at", "payload"]
        rows = [[
            rec.get("id"), rec.get("run_id"), rec.get("device_id"),
            rec.get("device"), rec.get("device_ip"), rec.get("cpu"),
            rec.get("memory"), rec.get("stp_state"), rec.get("stp_mode"),
            rec.get("stp_forward"), rec.get("stp_blocked"), rec.get("error_ports"),
            rec.get("error_total"), 1 if rec.get("healthy") else 0,
            rec.get("issues"), rec.get("error"), rec.get("inspected_at"),
            json.dumps(rec, ensure_ascii=False)] for rec in rows_in]
        return self._replace_rows("inspections", cols, rows)

    def save_monitors(self, rows_in: list) -> int:
        cols = ["id", "device_id", "device_name", "device_ip", "sysname",
                "serial", "version", "cpu", "memory", "ok", "error",
                "collected_at", "payload"]
        rows = [[
            rec.get("id"), rec.get("device_id"), rec.get("device"),
            rec.get("device_ip"), rec.get("sysname"), rec.get("serial"),
            rec.get("version"), rec.get("cpu"), rec.get("memory"),
            1 if rec.get("ok") else 0, rec.get("error"), rec.get("collected_at"),
            json.dumps(rec, ensure_ascii=False)] for rec in rows_in]
        return self._replace_rows("monitors", cols, rows)

    def save_metrics(self, rows_in: list) -> int:
        cols = ["id", "device_id", "device_name", "device_ip", "metric",
                "label", "value", "unit", "source", "collected_at", "payload"]
        rows = [[
            rec.get("id"), rec.get("device_id"), rec.get("device"),
            rec.get("device_ip"), rec.get("metric"), rec.get("label"),
            rec.get("value"), rec.get("unit"), rec.get("source"),
            rec.get("collected_at"),
            json.dumps(rec, ensure_ascii=False)] for rec in rows_in]
        return self._replace_rows("metrics", cols, rows)

    def save_alerts(self, rows_in: list) -> int:
        cols = ["id", "source", "source_display", "severity", "status",
                "device_ip", "device_name", "rule", "metric", "value",
                "content", "triggered_at", "assignee", "acknowledged_at",
                "acknowledged_by", "resolved_at", "resolved_by",
                "disposition_note", "payload"]
        rows = [[
            rec.get("id"), rec.get("source"), rec.get("source_display"),
            rec.get("severity"), rec.get("status"), rec.get("device_ip"),
            rec.get("device"), rec.get("rule"), rec.get("metric"),
            rec.get("value"), rec.get("content"), rec.get("triggered_at"),
            rec.get("assignee") or "", rec.get("acknowledged_at") or "",
            rec.get("acknowledged_by") or "", rec.get("resolved_at") or "",
            rec.get("resolved_by") or "", rec.get("disposition_note") or "",
            json.dumps(rec, ensure_ascii=False)] for rec in rows_in]
        return self._replace_rows("alerts", cols, rows)

    def alert_disposition(self, ids: list, status: str, assignee: str = "",
                          note: str = "", actor: str = "") -> int:
        """批量更新告警处置状态，并同步 payload，保证读接口立即生效。"""
        status = (status or "").strip().lower()
        labels = {"new": "未处理", "acknowledged": "已确认",
                  "resolved": "已恢复", "closed": "已关闭"}
        if status not in labels:
            raise ValueError("状态只能是 new / acknowledged / resolved / closed")
        clean_ids = [int(x) for x in (ids or []) if str(x).isdigit()]
        if not clean_ids:
            raise ValueError("至少选择一条告警")
        stamp = now_iso()
        changed = 0
        with self.connect() as conn:
            for alert_id in clean_ids:
                row = conn.execute("SELECT payload FROM alerts WHERE id=?", (alert_id,)).fetchone()
                if not row:
                    continue
                payload = json.loads(row["payload"] or "{}")
                payload["status"] = status
                payload["status_display"] = labels[status]
                if assignee:
                    payload["assignee"] = assignee[:64]
                if note:
                    payload["disposition_note"] = note[:500]
                ack_at = payload.get("acknowledged_at") or ""
                ack_by = payload.get("acknowledged_by") or ""
                resolved_at = payload.get("resolved_at") or ""
                resolved_by = payload.get("resolved_by") or ""
                if status in ("acknowledged", "resolved", "closed") and not ack_at:
                    ack_at, ack_by = stamp, actor[:64]
                if status in ("resolved", "closed"):
                    resolved_at, resolved_by = stamp, actor[:64]
                payload.update({"acknowledged_at": ack_at, "acknowledged_by": ack_by,
                                "resolved_at": resolved_at, "resolved_by": resolved_by})
                conn.execute(
                    "UPDATE alerts SET status=?, assignee=?, acknowledged_at=?,"
                    " acknowledged_by=?, resolved_at=?, resolved_by=?,"
                    " disposition_note=?, payload=? WHERE id=?",
                    (status, payload.get("assignee") or "", ack_at, ack_by,
                     resolved_at, resolved_by, payload.get("disposition_note") or "",
                     json.dumps(payload, ensure_ascii=False), alert_id))
                changed += 1
        return changed

    def backup_rows(self) -> list:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM backups ORDER BY mtime DESC").fetchall()
        return [json.loads(r["payload"] or "{}") for r in rows]

    def save_backups(self, rows: list) -> int:
        sql = ("INSERT OR REPLACE INTO backups(name,device_ip,size,mtime,payload,"
               "synced_at) VALUES(?,?,?,?,?,?)")
        with self.connect() as conn:
            for rec in rows:
                conn.execute(sql, [
                    rec.get("name") or rec.get("filename") or "",
                    rec.get("device_ip") or rec.get("ip") or "",
                    rec.get("size") or 0,
                    rec.get("mtime") or rec.get("modified") or "",
                    json.dumps(rec, ensure_ascii=False), now_iso()])
        return len(rows)

    # ------------------------------------------------------------ 读快照
    def devices(self, include_pending: bool = True) -> list:
        where = "" if include_pending else " WHERE pending_collection=0"
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload, pending_collection FROM devices" + where + " ORDER BY ip").fetchall()
        out = []
        for row in rows:
            try:
                item = json.loads(row["payload"] or "{}")
            except Exception:
                item = {}
            item["pending_collection"] = bool(row["pending_collection"])
            out.append(item)
        return out

    def inspections(self, hours: int | None = None, limit: int | None = None) -> list:
        sql = "SELECT payload FROM inspections"
        args: list[Any] = []
        if hours:
            sql += " WHERE inspected_at >= ?"
            args.append(_hours_ago(hours))
        sql += " ORDER BY inspected_at DESC, id DESC"
        if limit:
            sql += " LIMIT %d" % int(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [json.loads(r["payload"] or "{}") for r in rows]

    def monitors(self, hours: int | None = None, limit: int | None = None) -> list:
        sql = "SELECT payload FROM monitors"
        args: list[Any] = []
        if hours:
            sql += " WHERE collected_at >= ?"
            args.append(_hours_ago(hours))
        sql += " ORDER BY collected_at DESC, id DESC"
        if limit:
            sql += " LIMIT %d" % int(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [json.loads(r["payload"] or "{}") for r in rows]

    def metrics(self, hours: int | None = None, limit: int | None = None) -> list:
        sql = "SELECT payload FROM metrics"
        args: list[Any] = []
        if hours:
            sql += " WHERE collected_at >= ?"
            args.append(_hours_ago(hours))
        sql += " ORDER BY collected_at DESC, id DESC"
        if limit:
            sql += " LIMIT %d" % int(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [json.loads(r["payload"] or "{}") for r in rows]

    def alerts(self, hours: int | None = None, limit: int | None = None) -> list:
        sql = "SELECT payload FROM alerts"
        args: list[Any] = []
        if hours:
            sql += " WHERE triggered_at >= ?"
            args.append(_hours_ago(hours))
        sql += " ORDER BY triggered_at DESC, id DESC"
        if limit:
            sql += " LIMIT %d" % int(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [json.loads(r["payload"] or "{}") for r in rows]

    def counts(self) -> dict:
        with self.connect() as conn:
            def one(sql):
                return conn.execute(sql).fetchone()[0]
            return {
                "devices": one("SELECT count(*) FROM devices"),
                "inspections": one("SELECT count(*) FROM inspections"),
                "monitors": one("SELECT count(*) FROM monitors"),
                "metrics": one("SELECT count(*) FROM metrics"),
                "alerts": one("SELECT count(*) FROM alerts"),
                "backups": one("SELECT count(*) FROM backups"),
                "exports": one("SELECT count(*) FROM exports"),
                "ledger": one("SELECT count(*) FROM ledger"),
            }

    # ------------------------------------------------------------ 台账补充
    def ledger_all(self) -> dict:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM ledger").fetchall()
        return {r["device_ip"]: dict(r) for r in rows}

    def ledger_get(self, device_ip: str) -> dict:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM ledger WHERE device_ip=?",
                               (device_ip,)).fetchone()
        return dict(row) if row else {}

    def ledger_save(self, device_ip: str, values: dict) -> dict:
        current = self.ledger_get(device_ip)
        merged = {
            "device_ip": device_ip,
            "device_id": values.get("device_id", current.get("device_id")),
            "device_name": values.get("device_name", current.get("device_name", "")),
            "asset_no": values.get("asset_no", current.get("asset_no", "")),
            "owner": values.get("owner", current.get("owner", "")),
            "usage": values.get("usage", current.get("usage", "")),
            "location": values.get("location", current.get("location", "")),
            "warranty_until": values.get("warranty_until",
                                         current.get("warranty_until", "")),
            "kind_override": values.get("kind_override",
                                        current.get("kind_override", "")),
            "note": values.get("note", current.get("note", "")),
            "updated_at": now_iso(),
        }
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ledger(device_ip, device_id, device_name,"
                " asset_no, owner, usage, location, warranty_until, kind_override,"
                " note, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (merged["device_ip"], merged["device_id"], merged["device_name"],
                 merged["asset_no"], merged["owner"], merged["usage"],
                 merged["location"], merged["warranty_until"],
                 merged["kind_override"], merged["note"], merged["updated_at"]))
        return merged

    # ------------------------------------------------------------ 导出归档
    def add_export(self, kind: str, fmt: str, filename: str, rows: int,
                   params: dict | None = None, operator: str = "admin") -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO exports(kind, fmt, filename, rows, params, operator,"
                " created_at) VALUES(?,?,?,?,?,?,?)",
                (kind, fmt, filename, rows,
                 json.dumps(params or {}, ensure_ascii=False), operator, now_iso()))
            return cur.lastrowid

    def attach_export_file(self, export_id: int, path: str, sha256: str,
                           size: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE exports SET file_path=?, sha256=?, file_size=? WHERE id=?",
                         (path, sha256, int(size), int(export_id)))

    def exports(self, limit: int = 50) -> list:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exports ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["params"] = json.loads(item.get("params") or "{}")
            except Exception:
                item["params"] = {}
            out.append(item)
        return out

    def export(self, export_id: int) -> dict:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM exports WHERE id=?",
                               (export_id,)).fetchone()
        if not row:
            return {}
        item = dict(row)
        try:                                  # params 落库时是 JSON 文本，这里统一解成字典
            item["params"] = json.loads(item.get("params") or "{}")
        except Exception:
            item["params"] = {}
        return item


    # ------------------------------------------------------------ 设备台账（本平台维护）
    def device_upsert(self, device: dict) -> None:
        """新增/更新一台设备（自带采集模式下，台账由本平台维护）。"""
        payload = dict(device)
        payload.setdefault("source", "local")
        cols = ["id", "ip", "name", "vendor", "vendor_display", "model", "serial",
                "version", "role", "group_name", "region", "online", "pending_collection", "port",
                "last_online_at", "updated_at", "payload"]
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM devices WHERE ip=?",
                               (device.get("ip"),)).fetchone()
            if row and row["payload"]:
                try:
                    merged = json.loads(row["payload"])
                except Exception:
                    merged = {}
                merged.update({k: v for k, v in device.items() if v not in (None, "")})
                payload = merged
            existing_id = conn.execute("SELECT id FROM devices WHERE ip=?",
                                       (device.get("ip"),)).fetchone()
            payload["id"] = (existing_id["id"] if existing_id else
                             payload.get("id") or self._next_device_id(conn))
            conn.execute(
                "INSERT OR REPLACE INTO devices(%s,synced_at) VALUES(%s,?)"
                % (",".join(cols), ",".join("?" * len(cols))),
                [payload.get("id"), payload.get("ip"), payload.get("name"),
                 payload.get("vendor"), payload.get("vendor_display"),
                 payload.get("model"), payload.get("serial"), payload.get("version"),
                 payload.get("role"), payload.get("group"), payload.get("region"),
                 1 if payload.get("online", True) else 0,
                 1 if payload.get("pending_collection") else 0,
                 payload.get("port") or 22,
                 payload.get("last_online_at") or now_iso(),
                 payload.get("updated_at") or now_iso(),
                 json.dumps(payload, ensure_ascii=False), now_iso()])

    def device_mark(self, ip: str, values: dict) -> None:
        """更新设备 payload 里的运行状态字段（允许写 False / 空串，用于清除 last_error）。

        device_upsert 会跳过空值，适合"只填不改空"的台账字段；采集结果需要把
        online 改成 False、把 last_error 清空，所以单独走这个方法。
        """
        if not ip:
            return
        with self.connect() as conn:
            row = conn.execute("SELECT payload FROM devices WHERE ip=?", (ip,)).fetchone()
            if not row:
                return
            try:
                payload = json.loads(row["payload"] or "{}")
            except Exception:                               # noqa: BLE001
                payload = {}
            payload.update(values or {})
            payload["updated_at"] = payload.get("updated_at") or now_iso()
            conn.execute(
                "UPDATE devices SET payload=?, online=?, last_online_at=?, updated_at=?"
                " WHERE ip=?",
                (json.dumps(payload, ensure_ascii=False),
                 1 if payload.get("online") else 0,
                 payload.get("last_online_at") or "",
                 payload["updated_at"], ip))

    def _next_device_id(self, conn) -> int:
        row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM devices").fetchone()
        return int(row[0])

    def device_related_counts(self, ip: str) -> dict:
        """单台设备关联数据数量，用于删除确认和测试数据清理预览。"""
        counts = {}
        with self.connect() as conn:
            for key, table, column in (
                ("credentials", "credentials", "ip"),
                ("inspections", "inspections", "device_ip"),
                ("monitors", "monitors", "device_ip"),
                ("metrics", "metrics", "device_ip"),
                ("alerts", "alerts", "device_ip"),
                ("backups", "backups", "device_ip"),
                ("collect_logs", "collect_logs", "device_ip"),
                ("remote_sessions", "remote_sessions", "device_ip"),
                ("remote_commands", "remote_commands", "device_ip"),
            ):
                counts[key] = conn.execute(
                    "SELECT count(*) FROM %s WHERE %s=?" % (table, column), (ip,)).fetchone()[0]
            counts["ledger"] = conn.execute(
                "SELECT count(*) FROM ledger WHERE device_ip=?", (ip,)).fetchone()[0]
        return counts

    def demo_device_candidates(self) -> list:
        """列出测试/演示设备候选：10.20.* 地址或台账备注含“演示”。"""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT d.ip, d.name, d.vendor_display, d.model,"
                " COALESCE(l.note,'') AS ledger_note"
                " FROM devices d LEFT JOIN ledger l ON l.device_ip=d.ip"
                " WHERE d.ip LIKE '10.20.%' OR l.note LIKE '%演示%'"
                " ORDER BY d.ip").fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["counts"] = self.device_related_counts(item["ip"])
            out.append(item)
        return out

    def device_delete(self, ip: str, purge_history: bool = True) -> bool:
        """删除设备；purge_history=True 时同时清理该设备的全部关联数据。"""
        tables = (
            ("inspections", "device_ip"), ("monitors", "device_ip"),
            ("metrics", "device_ip"), ("alerts", "device_ip"),
            ("backups", "device_ip"), ("collect_logs", "device_ip"),
            ("remote_commands", "device_ip"), ("remote_sessions", "device_ip"),
            ("ledger", "device_ip"), ("credentials", "ip"),
        )
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM devices WHERE ip=?", (ip,)).fetchone()
            if not row:
                return False
            if purge_history:
                for table, column in tables:
                    conn.execute("DELETE FROM %s WHERE %s=?" % (table, column), (ip,))
            cur = conn.execute("DELETE FROM devices WHERE ip=?", (ip,))
            return bool(cur.rowcount)

    def device_get(self, ip: str) -> dict:
        with self.connect() as conn:
            row = conn.execute("SELECT payload, pending_collection FROM devices WHERE ip=?", (ip,)).fetchone()
        if not row or not row["payload"]:
            return {}
        try:
            item = json.loads(row["payload"])
        except Exception:
            return {}
        item["pending_collection"] = bool(row["pending_collection"])
        return item

    # ------------------------------------------------------------ 采集任务与日志
    def recent_inspections(self, ip: str, limit: int = 5) -> list:
        """某设备最近的巡检记录（新的在前），变化检测/持续高位判定用。"""
        if not ip:
            return []
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM inspections WHERE device_ip=?"
                " ORDER BY inspected_at DESC, id DESC LIMIT ?",
                (ip, int(limit))).fetchall()
        out = []
        for row in rows:
            try:
                out.append(json.loads(row["payload"] or "{}"))
            except Exception:
                continue
        return out

    def last_inspection(self, ip: str) -> dict:
        rows = self.recent_inspections(ip, limit=1)
        return rows[0] if rows else {}

    def collect_run_start(self, trigger: str = "manual", operator: str = "") -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO collect_runs(started_at, trigger, operator) VALUES(?,?,?)",
                (now_iso(), trigger, (operator or "")[:64]))
            return int(cur.lastrowid)

    def collect_run_finish(self, run_id: int, total: int, ok: int, failed: int,
                           skipped: int, duration_ms: int, message: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE collect_runs SET finished_at=?, total=?, ok=?, failed=?,"
                " skipped=?, duration_ms=?, message=? WHERE id=?",
                (now_iso(), total, ok, failed, skipped, int(duration_ms),
                 (message or "")[:500], run_id))

    def collect_log(self, run_id: int, device_ip: str, device_name: str, ok: bool,
                    reason: str, duration_ms: int, commands: str, summary: str,
                    raw_excerpt: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO collect_logs(run_id, device_ip, device_name, ok, reason,"
                " duration_ms, commands, summary, raw_excerpt, created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (run_id, device_ip, device_name, 1 if ok else 0, (reason or "")[:300],
                 int(duration_ms), (commands or "")[:2000], (summary or "")[:2000],
                 (raw_excerpt or "")[:8000], now_iso()))

    def collect_runs(self, limit: int = 20) -> list:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM collect_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def collect_logs(self, ip: str = "", limit: int = 50, run_id: int = 0,
                     only_failed: bool = False, with_raw: bool = True) -> list:
        sql = "SELECT * FROM collect_logs"
        where, args = [], []
        if ip:
            where.append("device_ip=?")
            args.append(ip)
        if run_id:
            where.append("run_id=?")
            args.append(int(run_id))
        if only_failed:
            where.append("ok=0")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
        if not with_raw:                       # 列表页不传大字段，省流量
            for row in rows:
                row.pop("raw_excerpt", None)
        return rows

    def collect_log_get(self, log_id: int) -> dict:
        """按 id 取一条采集日志（含原始回显摘要）。"""
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM collect_logs WHERE id=?",
                               (log_id,)).fetchone()
        return dict(row) if row else {}

    def last_collect_by_device(self) -> dict:
        """每台设备最近一次采集：{ip: {created_at, ok, summary, reason}}。"""
        out: dict = {}
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT device_ip, created_at, ok, summary, reason FROM collect_logs"
                " WHERE id IN (SELECT MAX(id) FROM collect_logs GROUP BY device_ip)"
            ).fetchall()
        for row in rows:
            out[row["device_ip"]] = {"created_at": row["created_at"],
                                    "ok": bool(row["ok"]),
                                    "summary": row["summary"] or "",
                                    "reason": row["reason"] or ""}
        return out

    def collect_stats(self, days: int = 7) -> dict:
        """近 N 天的采集统计（任务数 / 成功率 / 设备覆盖）。"""
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            runs = conn.execute(
                "SELECT count(*) FROM collect_runs WHERE started_at >= ?",
                (since,)).fetchone()[0]
            ok = conn.execute(
                "SELECT count(*) FROM collect_logs WHERE ok=1 AND created_at >= ?",
                (since,)).fetchone()[0]
            failed = conn.execute(
                "SELECT count(*) FROM collect_logs WHERE ok=0 AND created_at >= ?",
                (since,)).fetchone()[0]
            devices = conn.execute(
                "SELECT count(DISTINCT device_ip) FROM collect_logs WHERE ok=1"
                " AND created_at >= ?", (since,)).fetchone()[0]
        total = ok + failed
        return {"days": days, "runs": runs, "ok": ok, "failed": failed,
                "devices": devices,
                "success_rate": (round(100.0 * ok / total, 1) if total else None)}

    def purge_collect_logs(self, keep_days: int = 30) -> int:
        cutoff = (datetime.now() - timedelta(days=max(1, keep_days))).strftime(
            "%Y-%m-%d %H:%M:%S")
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM collect_logs WHERE created_at < ?", (cutoff,))
            conn.execute("DELETE FROM collect_runs WHERE started_at < ?", (cutoff,))
        return cur.rowcount

    def last_collect_at(self, ip: str) -> str:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT created_at FROM collect_logs WHERE device_ip=? AND ok=1"
                " ORDER BY id DESC LIMIT 1", (ip,)).fetchone()
        return row["created_at"] if row else ""


def _hours_ago(hours: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - hours * 3600))


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
        _store.init()
    return _store