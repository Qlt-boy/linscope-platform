# -*- coding: utf-8 -*-
"""平台账号体系：登录 / 退出 / 会话 / 角色权限 / 登录审计。

* **口令**：PBKDF2-HMAC-SHA256（20 万次迭代 + 每账号随机盐），库里只存摘要；
* **会话**：登录发一枚随机令牌，客户端放 `Authorization: Bearer <token>`；
  库里只存令牌的 SHA-256 摘要，可单独吊销、可设过期（记住我 30 天，否则 12 小时）；
* **角色**：`admin`（全部，含账号管理与系统设置）/ `operator`（台账、同步、远程登录等写操作）/
  `viewer`（只读 + 导出）；
* **审计**：登录、登录失败、退出、改口令、建号/停用/重置全部写 `auth_events`，
  远程登录会话也带上真实操作人。

首个管理员：库里没有账号时自动创建 `admin`（口令取 `NIP_ADMIN_PASSWORD`，
没有就随机生成并写到 `data/initial_admin_password.txt`，只提示一次）。
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta

from . import config
from .store import get_store

ROLES = {
    "admin": {"label": "超级管理员", "level": 3},
    "operator": {"label": "运维工程师", "level": 2},
    "viewer": {"label": "只读用户", "level": 1},
}
ROLE_LABELS = {key: value["label"] for key, value in ROLES.items()}
PBKDF2_ROUNDS = 200_000
SESSION_HOURS = 12
REMEMBER_DAYS = 30
LOCK_FAILURES = 5
LOCK_MINUTES = 10
MAX_ACTIVE_SESSIONS = 5


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "auth_error"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


# ------------------------------------------------------------------ 口令
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt,
                                 PBKDF2_ROUNDS)
    return "pbkdf2_sha256$%d$%s$%s" % (PBKDF2_ROUNDS, salt.hex(), digest.hex())


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_hex, digest_hex = (stored or "").split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"),
                                     bytes.fromhex(salt_hex), int(rounds))
        return secrets.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _now() -> datetime:
    return datetime.now()


def _stamp(moment: datetime | None = None) -> str:
    return (moment or _now()).strftime("%Y-%m-%d %H:%M:%S")


def password_problem(password: str) -> str:
    """口令强度检查（返回空串表示通过）。"""
    if not password or len(password) < 8:
        return "口令至少 8 位"
    kinds = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if kinds < 2:
        return "口令需包含大小写字母 / 数字 / 符号中的至少两类"
    return ""


# ------------------------------------------------------------------ 账号
def bootstrap_admin() -> dict | None:
    """库里没有账号时建一个管理员；返回新建信息（已存在则 None）。"""
    store = get_store()
    with store.connect() as conn:
        count = conn.execute("SELECT count(*) FROM users").fetchone()[0]
    if count:
        return None
    password = (os.environ.get("NIP_ADMIN_PASSWORD") or "").strip()
    generated = False
    if not password:
        password = "LinScope@" + secrets.token_urlsafe(6)
        generated = True
        path = os.path.join(str(config.DATA_DIR), "initial_admin_password.txt")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("初始管理员账号：admin\n初始口令：%s\n"
                             "（登录后请立刻在「账号」里改掉，然后删掉本文件）\n" % password)
        except OSError:
            pass
    user = create_user("admin", password, display_name="系统管理员",
                       role="admin", note="系统初始化创建", operator="system")
    log_event("admin", "bootstrap",
              detail="初始化管理员账号 admin；口令来源：%s"
                     % ("环境变量 NIP_ADMIN_PASSWORD" if not generated
                        else "随机生成，见 data/initial_admin_password.txt"))
    return {"username": user["username"], "password": password, "generated": generated}


def create_user(username: str, password: str, display_name: str = "", role: str = "viewer",
                note: str = "", operator: str = "system") -> dict:
    username = (username or "").strip()
    if not username or len(username) > 64:
        raise AuthError("账号名不能为空且不超过 64 字符")
    if role not in ROLES:
        raise AuthError("角色只能是 admin / operator / viewer")
    problem = password_problem(password)
    if problem:
        raise AuthError(problem)
    store = get_store()
    with store.connect() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
        if exists:
            raise AuthError("账号 %s 已存在" % username)
        conn.execute(
            "INSERT INTO users(username, display_name, role, password_hash, enabled, note,"
            " created_at, updated_at, password_changed_at) VALUES(?,?,?,?,1,?,?,?,?)",
            (username, display_name or username, role, hash_password(password), note,
             _stamp(), _stamp(), _stamp()))
    log_event(username, "create_user", "新建账号 %s（%s）" % (username, ROLE_LABELS[role]),
              operator=operator)
    return get_user(username) or {}


def get_user(username: str) -> dict | None:
    with get_store().connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return _user_view(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_store().connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _user_view(row) if row else None


def list_users() -> list:
    with get_store().connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        out = []
        for row in rows:
            item = _user_view(row)
            item["sessions"] = conn.execute(
                "SELECT count(*) FROM auth_sessions WHERE username=? AND revoked=0"
                " AND expires_at > ?", (item["username"], _stamp())).fetchone()[0]
            out.append(item)
    return out


def _user_view(row) -> dict:
    if row is None:
        return {}
    item = dict(row)
    item["enabled"] = bool(item.get("enabled"))
    item["role_label"] = ROLE_LABELS.get(item.get("role"), item.get("role"))
    item["is_admin"] = item.get("role") == "admin"
    item.pop("password_hash", None)
    return item


def update_user(user_id: int, payload: dict, operator: str = "admin") -> dict:
    target = get_user_by_id(user_id)
    if not target:
        raise AuthError("账号不存在", 404)
    fields, values = [], []
    if payload.get("display_name") is not None:
        fields.append("display_name=?")
        values.append(str(payload["display_name"])[:64])
    if payload.get("note") is not None:
        fields.append("note=?")
        values.append(str(payload["note"])[:200])
    if payload.get("role") is not None:
        role = str(payload["role"])
        if role not in ROLES:
            raise AuthError("角色只能是 admin / operator / viewer")
        if target["is_admin"] and role != "admin" and _admin_count() <= 1:
            raise AuthError("至少要保留一个超级管理员")
        fields.append("role=?")
        values.append(role)
    if payload.get("enabled") is not None:
        enabled = 1 if payload["enabled"] in (True, 1, "1", "true", "True") else 0
        if not enabled:
            if target["username"] == operator:
                raise AuthError("不能停用当前登录的账号")
            if target["is_admin"] and _admin_count() <= 1:
                raise AuthError("至少要保留一个启用的超级管理员")
        fields.append("enabled=?")
        values.append(enabled)
        if not enabled:
            revoke_user_sessions(target["username"])
    if not fields:
        raise AuthError("没有要修改的内容")
    fields.append("updated_at=?")
    values.append(_stamp())
    values.append(user_id)
    with get_store().connect() as conn:
        conn.execute("UPDATE users SET %s WHERE id=?" % ",".join(fields), values)
    log_event(target["username"], "update_user",
              "修改账号 %s：%s" % (target["username"],
                                 "、".join(f.split("=")[0] for f in fields if f != "updated_at=?")),
              operator=operator)
    return get_user_by_id(user_id) or {}


def delete_user(user_id: int, operator: str = "admin") -> dict:
    target = get_user_by_id(user_id)
    if not target:
        raise AuthError("账号不存在", 404)
    if target["username"] == operator:
        raise AuthError("不能删除当前登录的账号")
    if target["is_admin"] and _admin_count() <= 1:
        raise AuthError("至少要保留一个超级管理员")
    revoke_user_sessions(target["username"])
    with get_store().connect() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    log_event(target["username"], "delete_user", "删除账号 %s" % target["username"],
              operator=operator)
    return {"deleted": target["username"]}


def reset_password(user_id: int, password: str, operator: str = "admin") -> dict:
    target = get_user_by_id(user_id)
    if not target:
        raise AuthError("账号不存在", 404)
    problem = password_problem(password)
    if problem:
        raise AuthError(problem)
    with get_store().connect() as conn:
        conn.execute("UPDATE users SET password_hash=?, password_changed_at=?, updated_at=?"
                     " WHERE id=?", (hash_password(password), _stamp(), _stamp(), user_id))
    revoke_user_sessions(target["username"])
    log_event(target["username"], "reset_password", "重置账号 %s 的口令" % target["username"],
              operator=operator)
    return {"username": target["username"]}


def change_own_password(username: str, old_password: str, new_password: str) -> dict:
    user = get_user(username)
    if not user:
        raise AuthError("账号不存在", 404)
    with get_store().connect() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE username=?",
                           (username,)).fetchone()
    if not row or not verify_password(old_password, row["password_hash"]):
        raise AuthError("原口令不正确", 400, "bad_password")
    problem = password_problem(new_password)
    if problem:
        raise AuthError(problem)
    with get_store().connect() as conn:
        conn.execute("UPDATE users SET password_hash=?, password_changed_at=?, updated_at=?"
                     " WHERE username=?",
                     (hash_password(new_password), _stamp(), _stamp(), username))
    log_event(username, "password_change", "修改本人登录口令")
    return {"username": username}


def _admin_count() -> int:
    with get_store().connect() as conn:
        return conn.execute(
            "SELECT count(*) FROM users WHERE role='admin' AND enabled=1").fetchone()[0]


# ------------------------------------------------------------------ 会话
def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def login(username: str, password: str, client_ip: str = "", user_agent: str = "",
          remember: bool = False) -> dict:
    username = (username or "").strip()
    since = _stamp(_now() - timedelta(minutes=LOCK_MINUTES))
    with get_store().connect() as conn:
        # 成功登录或管理员重置口令都视为新的锁定周期起点。
        last_ok = conn.execute(
            "SELECT max(created_at) FROM auth_events"
            " WHERE username=? AND action IN ('login','reset_password')",
            (username,)).fetchone()[0] or ""
        start = max(since, last_ok or "")
        failures = conn.execute(
            "SELECT count(*) FROM auth_events WHERE username=? AND action='login_failed'"
            " AND created_at>=?", (username, start)).fetchone()[0]
        ip_failures = 0
        if client_ip:
            ip_failures = conn.execute(
                "SELECT count(*) FROM auth_events WHERE action='login_failed' AND ip=?"
                " AND created_at>=?", (client_ip, start)).fetchone()[0]
    if failures >= LOCK_FAILURES or ip_failures >= 20:
        log_event(username, "login_failed", "登录失败次数过多，账号临时锁定",
                  ip=client_ip, result="locked")
        raise AuthError("登录失败次数过多，请 %d 分钟后再试" % LOCK_MINUTES,
                        429, "locked")
    user = get_user(username)
    if not user:
        log_event(username, "login_failed", "账号不存在", ip=client_ip)
        raise AuthError("账号或口令不正确", 401, "bad_credentials")
    if not user["enabled"]:
        log_event(username, "login_failed", "账号已停用", ip=client_ip)
        raise AuthError("该账号已停用，请联系管理员", 403, "disabled")
    with get_store().connect() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE username=?",
                           (username,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        log_event(username, "login_failed", "口令错误", ip=client_ip)
        raise AuthError("账号或口令不正确", 401, "bad_credentials")

    token = secrets.token_urlsafe(32)
    hours = REMEMBER_DAYS * 24 if remember else SESSION_HOURS
    expires = _now() + timedelta(hours=hours)
    with get_store().connect() as conn:
        # 单账号只保留最近 N 个有效会话，防止长期累积导致会话面失控。
        conn.execute(
            "UPDATE auth_sessions SET revoked=1 WHERE username=? AND revoked=0 AND token_hash NOT IN ("
            "SELECT token_hash FROM auth_sessions WHERE username=? AND revoked=0 "
            "ORDER BY created_at DESC LIMIT ?)",
            (username, username, max(0, MAX_ACTIVE_SESSIONS - 1)))
        conn.execute(
            "INSERT INTO auth_sessions(token_hash, user_id, username, created_at, expires_at,"
            " last_seen_at, client_ip, user_agent, revoked) VALUES(?,?,?,?,?,?,?,?,0)",
            (_token_hash(token), user["id"], username, _stamp(), _stamp(expires), _stamp(),
             client_ip, (user_agent or "")[:200]))
        conn.execute("UPDATE users SET last_login_at=?, last_login_ip=? WHERE id=?",
                     (_stamp(), client_ip, user["id"]))
    log_event(username, "login", "登录成功", ip=client_ip)
    user = get_user(username) or {}
    user["session"] = {"created_at": _stamp(), "expires_at": _stamp(expires),
                       "client_ip": client_ip, "user_agent": (user_agent or "")[:200]}
    return {"token": token, "expires_at": _stamp(expires), "remember": bool(remember),
            "expires_hours": hours, "user": user}


def resolve(token: str) -> dict | None:
    """按令牌取当前用户；顺带刷新 last_seen（60 秒一次，别把库写爆）。"""
    if not token:
        return None
    token = token.strip()
    digest = _token_hash(token)
    with get_store().connect() as conn:
        row = conn.execute("SELECT * FROM auth_sessions WHERE token_hash=?",
                           (digest,)).fetchone()
        if not row or row["revoked"]:
            return None
        if row["expires_at"] and row["expires_at"] <= _stamp():
            conn.execute("UPDATE auth_sessions SET revoked=1 WHERE token_hash=?", (digest,))
            return None
        last = row["last_seen_at"] or ""
        if not last or (_now() - datetime.strptime(last, "%Y-%m-%d %H:%M:%S")).total_seconds() > 60:
            conn.execute("UPDATE auth_sessions SET last_seen_at=? WHERE token_hash=?",
                         (_stamp(), digest))
    user = get_user(row["username"])
    if not user or not user["enabled"]:
        return None
    user["token"] = token
    user["session"] = {"created_at": row["created_at"], "expires_at": row["expires_at"],
                       "client_ip": row["client_ip"], "user_agent": row["user_agent"]}
    return user


def logout(token: str, client_ip: str = "") -> bool:
    digest = _token_hash(token)
    with get_store().connect() as conn:
        row = conn.execute("SELECT username FROM auth_sessions WHERE token_hash=?",
                           (digest,)).fetchone()
        cur = conn.execute("UPDATE auth_sessions SET revoked=1 WHERE token_hash=?", (digest,))
    if row:
        log_event(row["username"], "logout", "退出登录", ip=client_ip)
    return bool(cur.rowcount)


def revoke_user_sessions(username: str) -> int:
    with get_store().connect() as conn:
        cur = conn.execute("UPDATE auth_sessions SET revoked=1 WHERE username=? AND revoked=0",
                           (username,))
    return cur.rowcount


def list_sessions(username: str | None = None, limit: int = 50) -> list:
    sql = "SELECT * FROM auth_sessions"
    args: list = []
    if username:
        sql += " WHERE username=?"
        args.append(username)
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    with get_store().connect() as conn:
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    now = _stamp()
    for row in rows:
        row["active"] = (not row["revoked"]) and (row["expires_at"] or "") > now
        row["token_hint"] = (row["token_hash"] or "")[:10]
        row.pop("token_hash", None)
        row.pop("user_id", None)
    return rows


def revoke_session_by_hint(hint: str, operator: str, allow_all: bool = False) -> int:
    with get_store().connect() as conn:
        sql = "UPDATE auth_sessions SET revoked=1 WHERE token_hash LIKE ? AND revoked=0"
        args = [hint + "%"]
        if not allow_all:
            sql += " AND username=?"
            args.append(operator)
        cur = conn.execute(sql, args)
    if cur.rowcount:
        log_event(operator, "revoke_session", "强制下线会话 %s…" % hint, operator=operator)
    return cur.rowcount


def log_event(username: str, action: str, detail: str = "", ip: str = "",
              operator: str = "", target_type: str = "account",
              result: str = "success") -> None:
    """写审计事件；username 是操作目标，actor 是真实操作者。"""
    try:
        actor = (operator or username or "system").strip()
        with get_store().connect() as conn:
            conn.execute(
                "INSERT INTO auth_events(username, action, detail, ip, actor,"
                " target_type, result, created_at) VALUES(?,?,?,?,?,?,?,?)",
                (username or "", action, (detail or "")[:300], ip or "",
                 actor, target_type or "", result or "success", _stamp()))
    except Exception:
        pass


def events(limit: int = 100, username: str = "", action: str = "",
           hours: int = 0) -> dict:
    sql = "SELECT * FROM auth_events"
    where, args = [], []
    if username:
        where.append("(username=? OR actor=?)")
        args.extend([username, username])
    if action:
        where.append("action=?")
        args.append(action)
    if hours and hours > 0:
        where.append("created_at >= ?")
        args.append(_stamp(_now() - timedelta(hours=int(hours))))
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with get_store().connect() as conn:
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    labels = {"login": "登录", "login_failed": "登录失败", "logout": "退出",
              "password_change": "修改口令", "create_user": "新建账号",
              "update_user": "修改账号", "delete_user": "删除账号",
              "reset_password": "重置口令", "revoke_session": "强制下线",
              "sftp_download": "SFTP 下载", "sftp_upload": "SFTP 上传",
              "sftp_mkdir": "SFTP 新建目录", "sftp_rename": "SFTP 重命名",
              "sftp_delete": "SFTP 删除", "bootstrap": "初始化",
              "api_write": "API 写操作", "permission_denied": "权限拒绝",
              "alert_disposition": "告警处置", "collect_run": "触发采集",
              "collect_settings": "修改采集设置", "collect_purge": "清理采集日志",
              "system_backup": "平台备份", "device_create": "新增设备",
              "device_update": "修改设备", "device_delete": "删除设备",
              "device_import": "导入设备", "demo_device_purge": "清理测试设备",
              "credential_update": "更新设备凭据",
              "credential_delete": "删除设备凭据", "archive_delete": "删除报告归档",
              "ssh_host_key_trusted": "固定 SSH 主机指纹",
              "ssh_host_key_changed": "SSH 主机指纹变化",
              "ssh_host_key_reset": "重置 SSH 主机指纹"}
    for row in rows:
        row["action_label"] = labels.get(row.get("action"), row.get("action"))
    failed = len([r for r in rows if r.get("action") == "login_failed"])
    return {"events": rows, "total": len(rows), "failed": failed,
            "action_labels": labels}


def overview(user: dict, client_ip: str = "") -> dict:
    """账号卡片 / 登录页需要的汇总：当前账号 + 权限 + 最近登录 + 账号统计。"""
    users = list_users() if user.get("is_admin") else []
    return {
        "user": {k: v for k, v in user.items() if k != "token"},
        "role_label": user.get("role_label"),
        "permissions": permissions_of(user),
        "last_login": {"at": user.get("last_login_at") or "",
                       "ip": user.get("last_login_ip") or ""},
        "session": user.get("session") or {},
        "client_ip": client_ip,
        "accounts": users,
        "session_limit": MAX_ACTIVE_SESSIONS,
        "counts": {
            "total": len(users) if users else None,
            "enabled": len([u for u in users if u["enabled"]]) if users else None,
            "admins": len([u for u in users if u["is_admin"]]) if users else None,
            "sessions": len(list_sessions(limit=200)),
        },
    }


def permissions_of(user: dict) -> dict:
    role = user.get("role") or "viewer"
    level = ROLES.get(role, {}).get("level", 1)
    return {
        "role": role,
        "role_label": ROLE_LABELS.get(role, role),
        "level": level,
        "read": True,
        "export": True,
        "ledger_write": level >= 2,          # 台账补充、批量导入
        "sync": level >= 2,                  # 触发采集 / 删除归档
        "remote": level >= 2,                # 远程登录（含凭据、控制台）
        "remote_full": level >= 3,          # 远程控制台全权限直通（超级管理员）
        "settings": level >= 3,              # 平台标识 / 采集设置 / 远程策略
        "users": level >= 3,                 # 账号管理
    }

