# -*- coding: utf-8 -*-
"""远程控制台：设备凭据保管 + SSH/SFTP + 命令留痕 + 危险命令策略。

设计边界（与「本平台只读消费巡检数据」并不冲突）：

* **设备清单来自本平台台账**：只有台账里登记过的 IP 才允许连（防止把平台当跳板）；
* **凭据由本平台加密保管**：设备口令用 Fernet 加密只存本地库，采集与远程登录共用；
  用 Fernet 对称加密，密钥放 `data/secret.key`（可用 `NIP_SECRET_KEY` 覆盖），口令永不回传前端；
* **每一次会话与每一条命令都留痕**：谁、什么时间、连了哪台设备、敲了什么、有没有被拦；
* **危险命令先拦后放**：命中策略的命令**不把回车发给设备**（block 直接 Ctrl+C 清行，confirm 等前端确认），
  避免「先执行再告警」这种假拦截。

SSH 走 paramiko，浏览器只拿 WebSocket，不在前端接触任何凭据。
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import posixpath
import queue
import re
import socket
import stat as statmod
import threading
import time
from datetime import datetime

from . import auth, config, service
from .store import get_store

try:                                            # paramiko 与 cryptography 是可选依赖：
    import paramiko                             # 缺了也能起服务，只是远程登录页会明确报错
except Exception:                               # pragma: no cover
    paramiko = None
try:
    from cryptography.fernet import Fernet
except Exception:                               # pragma: no cover
    Fernet = None

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SECRET_FILE = os.path.join(str(config.DATA_DIR), "secret.key")

# 默认命令策略：block = 直接拦下（连回车都不发）；confirm = 前端二次确认后才发回车
# 拆分口径：**破坏性/不可逆**的（格式化、清空配置、擦除启动文件）硬拦；
# 变更类但运维日常要用的（undo / delete / reboot / save）走人工确认。
DEFAULT_POLICY = {
    "mode": "confirm",                 # confirm / block / off
    "block_patterns": (
        r"\bformat\b",
        r"\bdelete\s*/\s*unreserved\b",
        r"\breset\s+saved-configuration\b",
        r"\berase\s+(startup-config|nvram|flash)\b",
        r"\bstartup\s+saved-configuration\s+\S+\s+erase\b",
        r"\bwrite\s+erase\b",
        r"\bdelete\s+flash:",
    ),
    "confirm_patterns": (
        r"^\s*(undo|delete|reset|reboot|no)\b",
        r"^\s*save\b",
        r"^\s*(startup|boot-loader)\b",
        r"^\s*(shutdown|undo\s+shutdown)\b",
        r"\b(config|system-view)\b",
    ),
    "auto_disable_paging": "1",        # 登录后自动关分屏
    "idle_timeout_seconds": "600",     # 前端无输入即断开，防止挂着没人管的会话
    "max_minutes": "120",              # 单会话最长时长
}

# 分屏命令按厂商各发一条（华为 screen-length / 华三 terminal length）
PAGING_COMMANDS = {
    "h3c": ["screen-length disable"],
    "huawei": ["screen-length 0 temporary"],
    "cisco": ["terminal length 0"],
    "other": ["screen-length disable"],
}


class RemoteError(Exception):
    """远程登录模块的业务错误（凭据缺失、目标不允许、连不上等）。"""


# ------------------------------------------------------------------ 凭据加密
def _secret_key() -> bytes:
    """取加密密钥：`NIP_SECRET_KEY` 优先，否则用 data/secret.key（首次自动生成）。"""
    env = (os.environ.get("NIP_SECRET_KEY") or "").strip()
    if env:
        return env.encode()
    path = os.environ.get("NIP_SECRET_FILE") or DEFAULT_SECRET_FILE
    if os.path.exists(path):
        with open(path, "rb") as handle:
            stored = handle.read().strip()
        if stored:
            return stored
    key = base64.urlsafe_b64encode(os.urandom(32))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(key)
    try:                                        # 尽量只给本用户读
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _fernet() -> "Fernet":
    if Fernet is None:
        raise RemoteError("缺少 cryptography 依赖，无法加密保管设备口令（pip install cryptography）")
    return Fernet(_secret_key())


def encrypt(text: str) -> str:
    if not text:
        return ""
    return _fernet().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except Exception as exc:
        raise RemoteError("凭据解密失败（密钥变过？）：%s" % exc)


# ------------------------------------------------------------------ 策略
def policy() -> dict:
    store = get_store()
    values = dict(DEFAULT_POLICY)
    try:
        with store.connect() as conn:
            for row in conn.execute("SELECT key, value FROM remote_policy"):
                values[row["key"]] = row["value"]
    except Exception:
        pass
    return values


def save_policy(values: dict) -> dict:
    store = get_store()
    current = policy()
    for key, value in (values or {}).items():
        if key not in DEFAULT_POLICY or value is None:
            continue
        if isinstance(value, (list, tuple)):
            value = "\n".join(str(v) for v in value if str(v).strip())
        current[key] = str(value)
    with store.connect() as conn:
        for key in DEFAULT_POLICY:
            conn.execute(
                "INSERT INTO remote_policy(key, value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, current[key]))
    service.cache_clear()
    return policy()


def _patterns(raw) -> list:
    """把策略里的正则列表解析出来（默认值是 tuple，库里存的是换行分隔的文本）。"""
    if isinstance(raw, (list, tuple)):
        lines = [str(item) for item in raw]
    else:
        lines = str(raw or "").splitlines()
    out = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(re.compile(line))
        except re.error:
            continue
    return out


def check_command(command: str, pol: dict | None = None) -> dict:
    """判定一条命令：ok / confirm / block。"""
    pol = pol or policy()
    text = (command or "").strip()
    if not text:
        return {"action": "ok", "reason": ""}
    mode = (pol.get("mode") or "confirm").lower()
    if mode == "off":
        return {"action": "ok", "reason": ""}
    for pattern in _patterns(pol.get("block_patterns", "")):
        if pattern.search(text):
            return {"action": "block", "reason": "命中禁止执行的高危模式：%s" % pattern.pattern}
    for pattern in _patterns(pol.get("confirm_patterns", "")):
        if pattern.search(text):
            return {"action": "confirm", "reason": "命中需确认的变更类模式：%s" % pattern.pattern}
    if mode == "block":                      # block 模式下，确认类也一并拦
        return {"action": "block", "reason": "当前策略为「一律拦截」，只放行查看类命令"}
    return {"action": "ok", "reason": ""}


# ------------------------------------------------------------------ 凭据
SECRET_MASK = "******"


def credentials_list() -> list:
    store = get_store()
    with store.connect() as conn:
        rows = conn.execute("SELECT * FROM credentials ORDER BY ip").fetchall()
    devices, _, _ = service.devices_view()
    meta = {d["ip"]: d for d in devices}
    out = []
    for row in rows:
        item = dict(row)
        dev = meta.get(item["ip"]) or {}
        out.append({
            "ip": item["ip"],
            "device_name": item.get("device_name") or dev.get("name") or "",
            "type_label": dev.get("type_label") or "",
            "port": item.get("port") or 22,
            "username": item.get("username") or "",
            "auth": item.get("auth") or "password",
            "has_secret": bool(item.get("secret_enc")),
            "has_key": bool(item.get("key_enc")),
            "vendor": item.get("vendor") or dev.get("vendor") or "",
            "note": item.get("note") or "",
            "updated_at": item.get("updated_at") or "",
            "updated_by": item.get("updated_by") or "",
            "host_key_fp": item.get("host_key_fp") or "",
            "host_key_at": item.get("host_key_at") or "",
            "registered": bool(dev),
        })
    return out


def credential_get(ip: str) -> dict:
    store = get_store()
    with store.connect() as conn:
        row = conn.execute("SELECT * FROM credentials WHERE ip=?", (ip,)).fetchone()
    return dict(row) if row else {}


def credential_save(ip: str, payload: dict, operator: str = "admin",
                    keep_secret: bool = True) -> dict:
    """保存/更新一台设备的登录凭据（口令只进不出，接口不回显）。"""
    ip = (ip or "").strip()
    if not ip:
        raise RemoteError("缺少设备 IP")
    devices, _, _ = devices_view_safe()
    dev = next((d for d in devices if d["ip"] == ip), None)
    if dev is None:
        pending, _, _ = service.devices_view(pending=True)
        dev = next((d for d in pending if d["ip"] == ip), None)
    if dev is None:
        raise RemoteError("设备 %s 不在待采集区或设备台账中，请先新增设备" % ip)

    current = credential_get(ip)
    username = (payload.get("username") or current.get("username") or "").strip()
    auth = (payload.get("auth") or current.get("auth") or "password").strip()
    if auth not in ("password", "key"):
        auth = "password"
    port = int(payload.get("port") or current.get("port") or 22)
    if not username:
        raise RemoteError("用户名不能为空")

    secret_enc = current.get("secret_enc") or ""
    key_enc = current.get("key_enc") or ""
    key_pass_enc = current.get("key_pass_enc") or ""
    if payload.get("password"):
        secret_enc = encrypt(str(payload["password"]))
    if payload.get("private_key"):
        key_enc = encrypt(str(payload["private_key"]))
    if payload.get("key_passphrase"):
        key_pass_enc = encrypt(str(payload["key_passphrase"]))
    if payload.get("clear_secret"):
        secret_enc = key_enc = key_pass_enc = ""
    if not keep_secret and not payload.get("password") and not payload.get("private_key"):
        raise RemoteError("请填写口令或私钥")

    if auth == "password" and not secret_enc:
        raise RemoteError("认证方式为口令，但还没有保存口令")
    if auth == "key" and not key_enc:
        raise RemoteError("认证方式为私钥，但还没有粘贴私钥内容")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_store().connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO credentials(ip, device_name, port, username, auth,"
            " secret_enc, key_enc, key_pass_enc, host_key_type, host_key_b64,"
            " host_key_fp, host_key_at, vendor, note, updated_at, updated_by)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ip, dev.get("name") or "", port, username, auth, secret_enc, key_enc,
             key_pass_enc, current.get("host_key_type") or "",
             current.get("host_key_b64") or "", current.get("host_key_fp") or "",
             current.get("host_key_at") or "", dev.get("vendor") or "",
             (payload.get("note") or "")[:200], stamp, operator))
    return {"ip": ip, "username": username, "port": port, "auth": auth,
            "has_secret": bool(secret_enc), "has_key": bool(key_enc),
            "updated_at": stamp}


def credential_delete(ip: str) -> bool:
    with get_store().connect() as conn:
        cur = conn.execute("DELETE FROM credentials WHERE ip=?", (ip,))
        return cur.rowcount > 0


def _size_text(size: int) -> str:
    value = float(size or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return ("%d %s" % (value, unit)) if unit == "B" else ("%.1f %s" % (value, unit))
        value /= 1024.0
    return "0 B"


def _sftp_client(ip: str, operator: str = ""):
    client, cred = _connect(ip, operator=operator)
    try:
        sftp = client.open_sftp()
    except Exception as exc:                           # noqa: BLE001
        try:
            client.close()
        except Exception:
            pass
        raise RemoteError("设备不支持 SFTP 或无法打开文件通道：%s" % exc)
    return client, sftp, cred


def _sftp_audit(operator: str, action: str, ip: str, path: str, client_ip: str = "") -> None:
    from . import auth
    auth.log_event(operator or "匿名", action, "%s %s" % (ip, path), client_ip or "")


def sftp_list(ip: str, path: str = "", operator: str = "") -> dict:
    """列出远端目录。返回统一字段，前端不需要接触 Paramiko。"""
    client = sftp = None
    try:
        client, sftp, _cred = _sftp_client(ip, operator)
        root = sftp.normalize((path or ".").strip() or ".")
        attrs = sftp.listdir_attr(root)
        entries = []
        for attr in attrs:
            mode = attr.st_mode or 0
            kind = "dir" if statmod.S_ISDIR(mode) else ("link" if statmod.S_ISLNK(mode) else "file")
            size = int(attr.st_size or 0)
            stamp = ""
            if attr.st_mtime:
                stamp = datetime.fromtimestamp(attr.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            entries.append({
                "name": attr.filename, "path": posixpath.join(root, attr.filename),
                "kind": kind, "size": size, "size_text": _size_text(size),
                "mtime": stamp, "mode": oct(mode & 0o777) if mode else "",
            })
        entries.sort(key=lambda row: (0 if row["kind"] == "dir" else 1, row["name"].lower()))
        parent = posixpath.dirname(root.rstrip("/")) or root
        if parent == root:
            parent = ""
        return {"ip": ip, "path": root, "parent": parent, "entries": entries,
                "total": len(entries)}
    except RemoteError:
        raise
    except Exception as exc:                           # noqa: BLE001
        raise RemoteError("SFTP 列目录失败：%s: %s" % (type(exc).__name__, exc))
    finally:
        if sftp is not None:
            try: sftp.close()
            except Exception: pass
        if client is not None:
            try: client.close()
            except Exception: pass


def sftp_download(ip: str, path: str, operator: str = "", client_ip: str = "") -> dict:
    """打开远端文件并返回按块读取的闭包；调用方负责通过 HTTP 流式返回。"""
    client = sftp = handle = None
    try:
        client, sftp, _cred = _sftp_client(ip, operator)
        remote_path = sftp.normalize((path or "").strip())
        attrs = sftp.stat(remote_path)
        if statmod.S_ISDIR(attrs.st_mode or 0):
            raise RemoteError("目标路径是目录，不能直接下载：%s" % remote_path)
        handle = sftp.open(remote_path, "rb")
        _sftp_audit(operator, "sftp_download", ip, remote_path, client_ip)

        def chunks():
            try:
                while True:
                    data = handle.read(64 * 1024)
                    if not data:
                        break
                    yield data
            finally:
                for closer in (handle, sftp, client):
                    try:
                        if closer is not None:
                            closer.close()
                    except Exception:
                        pass

        return {"name": posixpath.basename(remote_path), "path": remote_path,
                "size": int(attrs.st_size or 0), "chunks": chunks}
    except RemoteError:
        for closer in (handle, sftp, client):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass
        raise
    except Exception as exc:                           # noqa: BLE001
        for closer in (handle, sftp, client):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass
        raise RemoteError("SFTP 下载失败：%s: %s" % (type(exc).__name__, exc))


def sftp_upload(ip: str, path: str, name: str, data: bytes,
                operator: str = "", client_ip: str = "") -> dict:
    name = os.path.basename((name or "").replace("\\", "/")).strip()
    if not name or name in (".", ".."):
        raise RemoteError("上传文件名无效")
    client = sftp = None
    try:
        client, sftp, _cred = _sftp_client(ip, operator)
        root = sftp.normalize((path or ".").strip() or ".")
        target = posixpath.join(root, name)
        with sftp.file(target, "wb") as handle:
            handle.write(data)
        _sftp_audit(operator, "sftp_upload", ip, target, client_ip)
        return {"ok": True, "path": target, "size": len(data)}
    except RemoteError:
        raise
    except Exception as exc:                           # noqa: BLE001
        raise RemoteError("SFTP 上传失败：%s: %s" % (type(exc).__name__, exc))
    finally:
        if sftp is not None:
            try: sftp.close()
            except Exception: pass
        if client is not None:
            try: client.close()
            except Exception: pass


def sftp_mkdir(ip: str, path: str, name: str, operator: str = "",
               client_ip: str = "") -> dict:
    name = os.path.basename((name or "").replace("\\", "/")).strip()
    if not name or name in (".", ".."):
        raise RemoteError("目录名无效")
    client = sftp = None
    try:
        client, sftp, _cred = _sftp_client(ip, operator)
        root = sftp.normalize((path or ".").strip() or ".")
        target = posixpath.join(root, name)
        sftp.mkdir(target)
        _sftp_audit(operator, "sftp_mkdir", ip, target, client_ip)
        return {"ok": True, "path": target}
    except RemoteError:
        raise
    except Exception as exc:                           # noqa: BLE001
        raise RemoteError("SFTP 新建目录失败：%s: %s" % (type(exc).__name__, exc))
    finally:
        if sftp is not None:
            try: sftp.close()
            except Exception: pass
        if client is not None:
            try: client.close()
            except Exception: pass


def sftp_rename(ip: str, path: str, new_name: str, operator: str = "",
                client_ip: str = "") -> dict:
    new_name = os.path.basename((new_name or "").replace("\\", "/")).strip()
    if not new_name or new_name in (".", ".."):
        raise RemoteError("新名称无效")
    client = sftp = None
    try:
        client, sftp, _cred = _sftp_client(ip, operator)
        source = sftp.normalize((path or "").strip())
        target = posixpath.join(posixpath.dirname(source), new_name)
        sftp.rename(source, target)
        _sftp_audit(operator, "sftp_rename", ip, "%s -> %s" % (source, target), client_ip)
        return {"ok": True, "from": source, "to": target}
    except RemoteError:
        raise
    except Exception as exc:                           # noqa: BLE001
        raise RemoteError("SFTP 重命名失败：%s: %s" % (type(exc).__name__, exc))
    finally:
        if sftp is not None:
            try: sftp.close()
            except Exception: pass
        if client is not None:
            try: client.close()
            except Exception: pass


def sftp_delete(ip: str, path: str, operator: str = "", client_ip: str = "") -> dict:
    client = sftp = None
    try:
        client, sftp, _cred = _sftp_client(ip, operator)
        target = sftp.normalize((path or "").strip())
        attrs = sftp.stat(target)
        if statmod.S_ISDIR(attrs.st_mode or 0):
            sftp.rmdir(target)
            kind = "dir"
        else:
            sftp.remove(target)
            kind = "file"
        _sftp_audit(operator, "sftp_delete", ip, target, client_ip)
        return {"ok": True, "path": target, "kind": kind}
    except RemoteError:
        raise
    except Exception as exc:                           # noqa: BLE001
        raise RemoteError("SFTP 删除失败（目录需为空）：%s: %s"
                          % (type(exc).__name__, exc))
    finally:
        if sftp is not None:
            try: sftp.close()
            except Exception: pass
        if client is not None:
            try: client.close()
            except Exception: pass

def _load_pkey(key_text: str, passphrase: str = ""):
    classes = [paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey]
    dss = getattr(paramiko, "DSSKey", None)
    if dss is not None:
        classes.append(dss)
    for cls in classes:
        try:
            return cls.from_private_key(io.StringIO(key_text),
                                        password=passphrase or None)
        except Exception:
            continue
    raise RemoteError("私钥格式无法识别（支持 OpenSSH 的 RSA / ECDSA / Ed25519）")


def _host_key_fingerprint(key) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _probe_host_key(ip: str, port: int, timeout: float = 12.0) -> dict:
    """在认证前读取 SSH 主机公钥，用于首次信任与后续变更检测。"""
    if paramiko is None:
        raise RemoteError("缺少 paramiko 依赖（pip install paramiko）")
    sock = socket.create_connection((ip, int(port or 22)), timeout=timeout)
    transport = None
    try:
        transport = paramiko.Transport(sock)
        transport.start_client(timeout=timeout)
        key = transport.get_remote_server_key()
        return {"type": key.get_name(), "b64": key.get_base64(),
                "fp": _host_key_fingerprint(key)}
    except Exception as exc:                           # noqa: BLE001
        raise RemoteError("读取 SSH 主机指纹失败：%s: %s" % (type(exc).__name__, exc))
    finally:
        try:
            if transport is not None:
                transport.close()
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass


def _remember_host_key(ip: str, info: dict, operator: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_store().connect() as conn:
        conn.execute(
            "UPDATE credentials SET host_key_type=?, host_key_b64=?, host_key_fp=?,"
            " host_key_at=? WHERE ip=?",
            (info["type"], info["b64"], info["fp"], stamp, ip))
    auth.log_event(ip, "ssh_host_key_trusted", info["fp"], operator=operator,
                   target_type="device")


def _connect(ip: str, timeout: float = 12.0, operator: str = "admin"):
    """按凭据建一条 SSH 连接（调用方负责关闭）。"""
    if paramiko is None:
        raise RemoteError("缺少 paramiko 依赖（pip install paramiko）")
    cred = credential_get(ip)
    if not cred:
        raise RemoteError("设备 %s 还没有配置登录凭据" % ip)
    port = int(cred.get("port") or 22)
    host_info = _probe_host_key(ip, port, timeout)
    stored_fp = (cred.get("host_key_fp") or "").strip()
    if stored_fp and stored_fp != host_info["fp"]:
        auth.log_event(ip, "ssh_host_key_changed",
                       "原指纹 %s，新指纹 %s" % (stored_fp, host_info["fp"]),
                       operator=operator, target_type="device", result="denied")
        raise RemoteError("SSH 主机指纹变化：原 %s，当前 %s。已阻止连接，请核实设备或联系管理员重置指纹。"
                          % (stored_fp, host_info["fp"]))
    if not stored_fp:
        # 首次使用自动固定指纹（TOFU），后续任何变化都会阻断。
        _remember_host_key(ip, host_info, operator or "system")
    kwargs = {
        "hostname": ip,
        "port": port,
        "username": cred.get("username") or "",
        "timeout": timeout,
        "banner_timeout": timeout,
        "auth_timeout": timeout,
        "allow_agent": False,
        "look_for_keys": False,
    }
    if (cred.get("auth") or "password") == "key" and cred.get("key_enc"):
        kwargs["pkey"] = _load_pkey(decrypt(cred["key_enc"]),
                                    decrypt(cred.get("key_pass_enc") or ""))
    else:
        kwargs["password"] = decrypt(cred.get("secret_enc") or "")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    key_obj = paramiko.PKey.from_type_string(host_info["type"],
                                             base64.b64decode(host_info["b64"]))
    client.get_host_keys().add(ip, host_info["type"], key_obj)
    if int(port) != 22:
        client.get_host_keys().add("[%s]:%d" % (ip, int(port)),
                                   host_info["type"], key_obj)
    try:
        client.connect(**kwargs)
    except paramiko.AuthenticationException:
        client.close()
        raise RemoteError("认证失败：用户名 / 口令（或私钥）不对")
    except Exception as exc:
        try:
            client.close()
        except Exception:
            pass
        raise RemoteError("连接失败：%s: %s" % (type(exc).__name__, exc))
    return client, cred


def test_connection_candidate(ip: str, payload: dict, timeout: float = 12.0) -> dict:
    """测试尚未保存的 SSH 凭据，不写库、不固定主机指纹。"""
    import socket

    if paramiko is None:
        return {"ok": False, "stage": "dependency", "error": "缺少 paramiko 依赖"}
    payload = payload or {}
    current = credential_get(ip)
    username = (payload.get("username") or current.get("username") or "").strip()
    auth = (payload.get("auth") or current.get("auth") or "password").strip()
    if auth not in ("password", "key"):
        auth = "password"
    try:
        port = int(payload.get("port") or current.get("port") or 22)
    except Exception:
        return {"ok": False, "stage": "credential", "error": "SSH 端口必须是数字"}
    if not username:
        return {"ok": False, "stage": "credential", "error": "登录账号不能为空"}

    password = str(payload.get("password") or "")
    if not password and current.get("secret_enc"):
        password = decrypt(current.get("secret_enc") or "")
    private_key = str(payload.get("private_key") or "")
    if not private_key and current.get("key_enc"):
        private_key = decrypt(current.get("key_enc") or "")
    key_passphrase = str(payload.get("key_passphrase") or "")
    if not key_passphrase and current.get("key_pass_enc"):
        key_passphrase = decrypt(current.get("key_pass_enc") or "")
    if auth == "password" and not password:
        return {"ok": False, "stage": "credential", "error": "请输入登录口令"}
    if auth == "key" and not private_key.strip():
        return {"ok": False, "stage": "credential", "error": "请粘贴 OpenSSH 私钥内容"}

    started = time.time()
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
    except Exception as exc:
        return {"ok": False, "stage": "tcp", "error": "TCP %s:%s 不通：%s" % (ip, port, exc),
                "elapsed_ms": int((time.time() - started) * 1000)}
    finally:
        try:
            sock.close()
        except Exception:
            pass

    client = None
    try:
        host_info = _probe_host_key(ip, port, timeout)
        stored_fp = (current.get("host_key_fp") or "").strip()
        if stored_fp and stored_fp != host_info["fp"]:
            return {"ok": False, "stage": "ssh", "error": "SSH 主机指纹发生变化，请管理员核实后再保存",
                    "elapsed_ms": int((time.time() - started) * 1000)}
        kwargs = {
            "hostname": ip, "port": port, "username": username,
            "timeout": timeout, "banner_timeout": timeout, "auth_timeout": timeout,
            "allow_agent": False, "look_for_keys": False,
        }
        if auth == "key":
            kwargs["pkey"] = _load_pkey(private_key, key_passphrase)
        else:
            kwargs["password"] = password
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        key_obj = paramiko.PKey.from_type_string(host_info["type"], base64.b64decode(host_info["b64"]))
        client.get_host_keys().add(ip, host_info["type"], key_obj)
        if int(port) != 22:
            client.get_host_keys().add("[%s]:%d" % (ip, int(port)), host_info["type"], key_obj)
        client.connect(**kwargs)
        transport = client.get_transport()
        return {
            "ok": True, "stage": "ready", "elapsed_ms": int((time.time() - started) * 1000),
            "username": username, "port": port,
            "ssh_version": getattr(transport, "remote_version", "") or "",
            "hint": "连接测试通过，可以保存凭据",
        }
    except paramiko.AuthenticationException:
        return {"ok": False, "stage": "ssh", "error": "认证失败：账号 / 口令（或私钥）不正确",
                "elapsed_ms": int((time.time() - started) * 1000)}
    except Exception as exc:
        return {"ok": False, "stage": "ssh", "error": "连接失败：%s: %s" % (type(exc).__name__, exc),
                "elapsed_ms": int((time.time() - started) * 1000)}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def test_connection(ip: str, timeout: float = 12.0) -> dict:
    """连通性 + 认证测试：把「TCP 通不通 / 认证过不过 / 是什么设备」分开报。"""
    import socket
    cred = credential_get(ip)
    if not cred:
        return {"ok": False, "stage": "credential", "error": "还没有配置登录凭据"}
    port = int(cred.get("port") or 22)
    started = time.time()
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
    except Exception as exc:
        return {"ok": False, "stage": "tcp", "error": "TCP %s:%s 不通：%s"
                % (ip, port, exc), "elapsed_ms": int((time.time() - started) * 1000)}
    finally:
        try:
            sock.close()
        except Exception:
            pass
    try:
        client, _ = _connect(ip, timeout)
    except RemoteError as exc:
        return {"ok": False, "stage": "ssh", "error": str(exc),
                "elapsed_ms": int((time.time() - started) * 1000)}
    try:
        transport = client.get_transport()
        banner = ""
        try:
            stdin, stdout, stderr = client.exec_command("display version", timeout=8)
            banner = (stdout.read(2000) or b"").decode("utf-8", "replace").strip()
        except Exception:
            pass
        return {
            "ok": True, "stage": "ready",
            "elapsed_ms": int((time.time() - started) * 1000),
            "username": cred.get("username"), "port": port,
            "ssh_version": getattr(transport, "remote_version", "") or "",
            "banner_head": "\n".join(banner.splitlines()[:4]),
            "hint": "认证通过，返回后即可打开控制台",
        }
    finally:
        try:
            client.close()
        except Exception:
            pass


# ------------------------------------------------------------------ 会话与留痕
def _log_session_start(ip: str, device_name: str, username: str, operator: str,
                       client_ip: str) -> int:
    with get_store().connect() as conn:
        cur = conn.execute(
            "INSERT INTO remote_sessions(device_ip, device_name, username, operator,"
            " client_ip, started_at, status) VALUES(?,?,?,?,?,?,'running')",
            (ip, device_name, username, operator, client_ip,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        return cur.lastrowid


def _log_session_end(session_id: int, status: str, commands: int, blocked: int,
                     error: str = "") -> None:
    with get_store().connect() as conn:
        conn.execute(
            "UPDATE remote_sessions SET ended_at=?, status=?, commands=?, blocked=?,"
            " error=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status, commands, blocked,
             error[:400], session_id))


def _log_command(session_id: int, ip: str, command: str, action: str,
                 reason: str = "") -> None:
    with get_store().connect() as conn:
        conn.execute(
            "INSERT INTO remote_commands(session_id, device_ip, command, action,"
            " reason, created_at) VALUES(?,?,?,?,?,?)",
            (session_id, ip, command[:500], action, reason[:200],
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))


def sessions(limit: int = 50, ip: str = "") -> dict:
    store = get_store()
    sql = "SELECT * FROM remote_sessions"
    args: list = []
    if ip:
        sql += " WHERE device_ip=?"
        args.append(ip)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with store.connect() as conn:
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    for row in rows:
        row["commands"] = row.get("commands") or 0
        row["blocked"] = row.get("blocked") or 0
    running = len([r for r in rows if r.get("status") == "running"])
    failed = len([r for r in rows if r.get("status") == "error"])
    return {"sessions": rows, "total": len(rows), "running": running,
            "failed": failed,
            "devices": len({r["device_ip"] for r in rows if r.get("device_ip")})}


def session_commands(session_id: int, limit: int = 500) -> dict:
    with get_store().connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM remote_commands WHERE session_id=? ORDER BY id LIMIT ?",
            (session_id, limit)).fetchall()]
    return {"session_id": session_id, "commands": rows, "total": len(rows),
            "blocked": len([r for r in rows if r.get("action") == "block"])}


# ------------------------------------------------------------------ 行重组（把按键流还原成命令）
class LineAssembler:
    """把 SSH 通道上的按键流重组成「一行命令」。

    作用有二：① 会话留痕（谁敲了什么）；② 在回车**之前**判定危险命令——命中就不把
    回车发给设备，避免「先执行后告警」。
    """

    def __init__(self):
        self.buffer = ""

    def feed(self, data: str) -> str | None:
        """返回刚敲完的一行（含回车/换行时），否则 None。"""
        line = None
        for ch in data:
            if ch in ("\r", "\n"):
                line = self.buffer.strip()
                self.buffer = ""
                if line:
                    return line
                line = None
            elif ch in ("\x7f", "\b"):
                self.buffer = self.buffer[:-1]
            elif ch == "\x03":                      # Ctrl+C：本行作废
                self.buffer = ""
            elif ch in ("\x15", "\x0b"):            # Ctrl+U / Ctrl+K：清行
                self.buffer = ""
            elif ch == "\t":
                continue
            elif ch == "\x1b":                      # 方向键等转义序列直接忽略
                continue
            elif ord(ch) < 32:
                continue
            else:
                self.buffer += ch
        return line

    def pending(self) -> str:
        return self.buffer


SESSION_MANAGER_LOCK = threading.Lock()
ACTIVE_SESSIONS: dict = {}

# ------------------------------------------------------------------ 会话桥（paramiko ↔ WebSocket）
class RemoteSession:
    """一条远程登录会话：SSH shell 通道 ↔ 前端 WebSocket 的双向搬运。

    线程模型：本对象在**线程**里跑（paramiko 是阻塞的），事件通过 `emit` 回调丢回
    asyncio 事件循环；前端发来的按键进 `inbox` 队列由本线程转发给设备。
    """

    def __init__(self, ip: str, device_name: str, operator: str, client_ip: str,
                 cols: int = 120, rows: int = 32, emit=None,
                 unrestricted: bool = False):
        self.ip = ip
        self.unrestricted = bool(unrestricted)
        self.device_name = device_name
        self.operator = operator
        self.client_ip = client_ip
        self.cols = max(40, min(400, int(cols or 120)))
        self.rows = max(10, min(200, int(rows or 32)))
        self.emit = emit or (lambda event: None)
        self.inbox: "queue.Queue" = queue.Queue()
        self.stop_flag = threading.Event()
        self.pending_size = None
        self.asm = LineAssembler()
        self.client = None
        self.channel = None
        self.session_id = None
        self.commands = 0
        self.blocked = 0
        self.confirm_seq = 0
        self.waiting_confirm = None
        self.started_at = time.time()
        self.close_reason = ""
        self.username = ""
        self.policy = {}
        self.held: list = []            # 等待人工确认期间先按住按键，别把下一条命令拼进设备

    # ---------------- 前端 → 会话
    def send(self, data: str) -> None:
        if data:
            self.inbox.put(("data", data))

    def resize(self, cols: int, rows: int) -> None:
        self.pending_size = (max(40, min(400, int(cols or 120))),
                             max(10, min(200, int(rows or 32))))

    def confirm(self, allow: bool) -> None:
        self.inbox.put(("confirm", bool(allow)))

    def close(self, reason: str = "客户端断开") -> None:
        self.close_reason = reason
        self.stop_flag.set()

    # ---------------- 主循环
    def run(self) -> None:
        pol = dict(policy())
        if self.unrestricted:
            pol["mode"] = "full"
        self.policy = pol
        try:
            self.client, cred = _connect(self.ip, operator=self.operator)
        except RemoteError as exc:
            self._emit_notice("error", str(exc))
            self._emit({"type": "closed", "reason": str(exc)})
            self._finish("error", str(exc))
            return

        self.username = cred.get("username") or ""
        try:
            self.channel = self.client.invoke_shell(term="xterm", width=self.cols,
                                                    height=self.rows)
            self.channel.settimeout(0.2)
        except Exception as exc:
            self._emit_notice("error", "无法打开交互式 shell：%s" % exc)
            self._emit({"type": "closed", "reason": str(exc)})
            self._finish("error", str(exc))
            self._close_client()
            return

        self.session_id = _log_session_start(self.ip, self.device_name, self.username,
                                             self.operator, self.client_ip)
        self._emit({"type": "ready", "session": {
            "id": self.session_id, "device_ip": self.ip,
            "device_name": self.device_name, "username": self.username,
            "operator": self.operator, "policy": self.policy.get("mode"),
            "unrestricted": self.unrestricted,
        }})
        if str(self.policy.get("auto_disable_paging", "1")).lower() in ("1", "true", "yes", "on"):
            self._disable_paging(cred.get("vendor") or "")

        idle_limit = max(60, int(self.policy.get("idle_timeout_seconds") or 600))
        max_limit = max(60, int(self.policy.get("max_minutes") or 120)) * 60
        last_input = time.time()
        status = "closed"
        error = ""
        try:
            while not self.stop_flag.is_set():
                if self.pending_size:
                    cols, rows = self.pending_size
                    self.pending_size = None
                    try:
                        self.channel.resize_pty(width=cols, height=rows)
                    except Exception:
                        pass
                if time.time() - last_input > idle_limit:
                    self._emit_notice("warn", "空闲超过 %d 秒，会话自动断开" % idle_limit)
                    status = "timeout"
                    break
                if time.time() - self.started_at > max_limit:
                    self._emit_notice("warn", "会话达到最长时长 %d 分钟，已断开"
                                      % (max_limit // 60))
                    status = "timeout"
                    break

                # 设备 → 前端
                try:
                    data = self.channel.recv(65536)
                except Exception:
                    data = b""
                if data:
                    self._emit({"type": "output",
                                "data": data.decode("utf-8", "replace")})

                # 前端 → 设备
                drained = 0
                while drained < 200:
                    try:
                        kind, payload = self.inbox.get_nowait()
                    except queue.Empty:
                        break
                    drained += 1
                    if kind == "data":
                        last_input = time.time()
                        if self.waiting_confirm:
                            self.held.append(payload)   # 确认未决期间冻结输入
                        else:
                            self._forward_keystrokes(payload)
                    elif kind == "confirm":
                        self._resolve_confirm(payload)
                if self.channel.closed or self.channel.exit_status_ready():
                    self._emit_notice("warn", "设备侧已关闭该会话")
                    break
        except Exception as exc:                     # noqa: BLE001
            status, error = "error", "%s: %s" % (type(exc).__name__, exc)
            self._emit_notice("error", "会话异常：%s" % error)
        finally:
            self._finish(status, error)
            self._close_client()
            self._emit({"type": "closed", "reason": getattr(self, "close_reason", "")
                        or ("会话结束（%s）" % status)})

    # ---------------- 内部
    def _forward_keystrokes(self, payload: str) -> None:
        """逐字符转发；回车前先过命令策略（命中就**不发回车**）。"""
        out = []
        for ch in payload:
            if ch in ("\r", "\n"):
                line = self.asm.buffer.strip()
                self.asm.buffer = ""
                if not line:
                    out.append(ch)                   # 空行原样回车
                    continue
                if self.unrestricted:
                    self.commands += 1
                    _log_command(self.session_id, self.ip, line, "sent", "全权限终端")
                    self._emit({"type": "command",
                                "command": {"command": line, "action": "sent",
                                            "reason": "全权限终端",
                                            "created_at": _now()}})
                    out.append("\r")
                    continue
                decision = check_command(line, self.policy)
                if decision["action"] == "block":
                    self.blocked += 1
                    _log_command(self.session_id, self.ip, line, "block",
                                 decision["reason"])
                    out.append("\x03")               # Ctrl+C 清掉设备侧那行
                    self._emit_notice("error", "已拦截：%s（%s）"
                                      % (line, decision["reason"]))
                    self._emit({"type": "command",
                                "command": {"command": line, "action": "block",
                                            "reason": decision["reason"],
                                            "created_at": _now()}})
                elif decision["action"] == "confirm":
                    self.confirm_seq += 1
                    self.waiting_confirm = {"command": line,
                                            "reason": decision["reason"]}
                    self._emit({"type": "confirm", "id": self.confirm_seq,
                                "command": line, "reason": decision["reason"]})
                else:
                    self.commands += 1
                    _log_command(self.session_id, self.ip, line, "sent")
                    self._emit({"type": "command",
                                "command": {"command": line, "action": "sent",
                                            "reason": "", "created_at": _now()}})
                    out.append("\r")
            else:
                self.asm.feed(ch)
                out.append(ch)
        if out:
            try:
                self.channel.send("".join(out))
            except Exception:
                pass

    def _resolve_confirm(self, allow: bool) -> None:
        waiting = self.waiting_confirm
        self.waiting_confirm = None
        if not waiting:
            return
        line = waiting["command"]
        held = self.held
        self.held = []
        if allow:
            self.commands += 1
            _log_command(self.session_id, self.ip, line, "sent", "人工确认后放行")
            self._emit({"type": "command",
                        "command": {"command": line, "action": "sent",
                                    "reason": "人工确认后放行",
                                    "created_at": _now()}})
            try:
                self.channel.send("\r")
            except Exception:
                pass
        else:
            self.blocked += 1
            _log_command(self.session_id, self.ip, line, "cancel", "人工取消")
            self._emit_notice("warn", "已取消：%s%s" % (
                line, "（确认期间键入的内容已丢弃）" if held else ""))
            self._emit({"type": "command",
                        "command": {"command": line, "action": "cancel",
                                    "reason": "人工取消", "created_at": _now()}})
            try:
                self.channel.send("\x03")
            except Exception:
                pass
        if held:
            # 确认未决期间的按键一律丢弃：补发会拼进下一行，反而容易出事故
            self._emit_notice("warn", "确认期间的输入已丢弃（%d 段），请重新输入" % len(held))

    def _disable_paging(self, vendor: str) -> None:
        commands = PAGING_COMMANDS.get((vendor or "").lower(), PAGING_COMMANDS["other"])
        try:
            for command in commands:
                self.channel.send(command + "\n")
                time.sleep(0.35)
        except Exception:
            pass

    def _finish(self, status: str, error: str = "") -> None:
        if self.session_id:
            _log_session_end(self.session_id, status, self.commands, self.blocked, error)

    def _close_client(self) -> None:
        for closer in (self.channel, self.client):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass

    def _emit(self, event: dict) -> None:
        try:
            self.emit(event)
        except Exception:
            pass

    def _emit_notice(self, level: str, text: str) -> None:
        self._emit({"type": "notice", "level": level, "text": text})


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def console_category(device: dict) -> str:
    """远程控制台三板块归类：switch / server / security。"""
    group_kind = str((device or {}).get("group_kind") or "")
    text = " ".join(str((device or {}).get(k) or "") for k in
                    ("name", "type_label", "kind", "group", "model", "vendor",
                     "vendor_display")).lower()
    security_words = ("防火墙", "安全", "vpn", "waf", "ips", "ids", "utm",
                      "firewall", "fortinet", "sangfor", "深信服", "奇安信", "天融信")
    if any(word in text for word in security_words):
        return "security"
    if group_kind == "server" or any(word in text for word in
                                     ("服务器", "linux", "windows", "server")):
        return "server"
    return "switch"


CONSOLE_CATEGORY_LABELS = {"switch": "交换机", "server": "服务器", "security": "安全设备"}

def remote_overview() -> dict:
    """远程控制台概览：交换机/服务器/安全设备、凭据状态、会话统计与依赖自检。"""
    devices, source, info = devices_view_safe()
    creds = {c["ip"]: c for c in credentials_list()}
    rows = []
    for dev in devices:
        cred = creds.get(dev["ip"])
        category = console_category(dev)
        rows.append({
            "id": dev["id"], "ip": dev["ip"], "name": dev["name"],
            "type_label": dev["type_label"], "model": dev["model"],
            "vendor": dev["vendor_display"], "group": dev["group"],
            "region": dev["region"], "online": dev["online"],
            "kind": dev.get("kind") or "", "group_kind": dev.get("group_kind") or "",
            "category": category, "category_label": CONSOLE_CATEGORY_LABELS[category],
            "health_label": dev["health_label"], "health_tone": dev["health_tone"],
            "credential": {
                "configured": bool(cred),
                "username": (cred or {}).get("username") or "",
                "port": (cred or {}).get("port") or 22,
                "auth": (cred or {}).get("auth") or "password",
                "updated_at": (cred or {}).get("updated_at") or "",
            },
        })
    stats = sessions(limit=200)
    ready = len([r for r in rows if r["credential"]["configured"]])
    categories = {}
    for key, label in CONSOLE_CATEGORY_LABELS.items():
        subset = [r for r in rows if r["category"] == key]
        categories[key] = {
            "key": key, "label": label, "total": len(subset),
            "credential_ready": len([r for r in subset if r["credential"]["configured"]]),
        }
    return {
        "source": source, "source_info": info,
        "devices": rows, "total": len(rows), "credential_ready": ready,
        "credential_missing": len(rows) - ready, "categories": categories,
        "sessions": stats,
        "policy": policy(),
        "policy_defaults": DEFAULT_POLICY,
        "dependencies": {
            "paramiko": paramiko is not None,
            "cryptography": Fernet is not None,
        },
    }


def devices_view_safe():
    """设备台账取数（上游不可达时回落本地台账/镜像，不让远程页整体报错）。"""
    try:
        return service.devices_view()
    except Exception:
        store = get_store()
        rows = [service.nz.device_view(dev, None, None,
                                       (store.ledger_all() or {}).get(dev.get("ip")))
                for dev in store.devices()]
        return rows, "local", {"error": "上游数据源不可达，已回落本地台账"}




