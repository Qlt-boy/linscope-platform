# -*- coding: utf-8 -*-
"""平台一致性备份与运行体检。

备份内容：SQLite 一致性快照、设备凭据密钥、TLS 证书、配置备份、初始化凭据文件。
备份文件保存在数据卷 platform-backups/，默认保留最近 7 份。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

from . import config

BACKUP_DIR = config.DATA_DIR / "platform-backups"


def _backup_keep() -> int:
    try:
        return max(1, min(90, int(os.environ.get("NIP_BACKUP_KEEP", "7"))))
    except ValueError:
        return 7


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_backup(reason: str = "manual", actor: str = "system") -> dict:
    """创建一份一致性 ZIP 备份，返回文件名、大小和 SHA256。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = "linscope-backup-%s-%s.zip" % (stamp, reason)
    target = BACKUP_DIR / name
    tmp_db = BACKUP_DIR / (".tmp-%s.sqlite3" % stamp)
    try:
        src = sqlite3.connect(str(config.DB_PATH), timeout=30)
        dst = sqlite3.connect(str(tmp_db))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        manifest = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reason": reason,
            "actor": actor,
            "db_sha256": _sha256(tmp_db),
            "version": "1.3.0",
        }
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6) as zf:
            zf.write(tmp_db, "netinspect.sqlite3")
            for rel in ("secret.key", "initial_admin_password.txt", ".demo-seeded"):
                path = config.DATA_DIR / rel
                if path.is_file():
                    zf.write(path, rel)
            for dirname in ("tls", "config-backups", "report-archive"):
                base = config.DATA_DIR / dirname
                if base.is_dir():
                    for path in base.rglob("*"):
                        if path.is_file():
                            zf.write(path, str(Path(dirname) / path.relative_to(base)))
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    finally:
        try:
            if tmp_db.exists():
                tmp_db.unlink()
        except OSError:
            pass

    info = {"name": name, "size": target.stat().st_size,
            "sha256": _sha256(target),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reason": reason, "actor": actor}
    (BACKUP_DIR / (name + ".json")).write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    prune()
    return info


def list_backups(limit: int = 20) -> list:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(BACKUP_DIR.glob("linscope-backup-*.zip"), reverse=True)[:limit]:
        meta_path = BACKUP_DIR / (path.name + ".json")
        info = {}
        try:
            info = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        info.update({"name": path.name, "size": path.stat().st_size,
                     "modified_at": datetime.fromtimestamp(path.stat().st_mtime).strftime(
                         "%Y-%m-%d %H:%M:%S")})
        rows.append(info)
    return rows


def get_backup_path(name: str) -> Path | None:
    safe = os.path.basename(name or "")
    if safe != name or not safe.startswith("linscope-backup-") or not safe.endswith(".zip"):
        return None
    path = BACKUP_DIR / safe
    return path if path.is_file() else None


def prune() -> None:
    keep = _backup_keep()
    files = sorted(BACKUP_DIR.glob("linscope-backup-*.zip"), reverse=True)
    for path in files[keep:]:
        try:
            path.unlink()
            meta = BACKUP_DIR / (path.name + ".json")
            if meta.exists():
                meta.unlink()
        except OSError:
            pass


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
    except OSError:
        pass
    return total


def diagnostics() -> dict:
    from cryptography import x509
    from .collect import scheduler

    disk = shutil.disk_usage(str(config.DATA_DIR))
    db_path = Path(config.DB_PATH)
    cert_path = config.DATA_DIR / "tls" / "server.crt"
    cert = {}
    if cert_path.is_file():
        try:
            parsed = x509.load_pem_x509_certificate(cert_path.read_bytes())
            cert = {
                "subject": parsed.subject.rfc4514_string(),
                "expires_at": parsed.not_valid_after_utc.isoformat(),
                "days_left": max(0, (parsed.not_valid_after_utc - datetime.now(
                    parsed.not_valid_after_utc.tzinfo)).days),
            }
        except Exception:
            cert = {"error": "证书读取失败"}
    backups = list_backups(limit=5)
    return {
        "data_dir": str(config.DATA_DIR),
        "data_size_bytes": _dir_size(config.DATA_DIR),
        "database_size_bytes": db_path.stat().st_size if db_path.is_file() else 0,
        "disk_total_bytes": disk.total,
        "disk_free_bytes": disk.free,
        "disk_free_percent": round(100.0 * disk.free / disk.total, 1) if disk.total else 0,
        "tls": cert,
        "scheduler": scheduler.state(),
        "backups": backups,
        "auto_backup_hours": os.environ.get("NIP_AUTO_BACKUP_HOURS", "24"),
        "backup_keep": _backup_keep(),
    }


def start_scheduler() -> None:
    """后台自动备份线程；周期由 NIP_AUTO_BACKUP_HOURS 控制，0 表示关闭。"""
    try:
        hours = float(os.environ.get("NIP_AUTO_BACKUP_HOURS", "24"))
    except ValueError:
        hours = 24
    if hours <= 0:
        return

    def loop() -> None:
        while True:
            time.sleep(max(300, int(hours * 3600)))
            try:
                create_backup("scheduled", "scheduler")
            except Exception:
                pass

    threading.Thread(target=loop, daemon=True, name="platform-backup").start()
