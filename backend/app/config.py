# -*- coding: utf-8 -*-
"""平台配置：环境变量 / backend/.env / 数据库里可在线修改的设置。

优先级：数据库设置（页面里改的） > 环境变量 / .env > 内置默认值。
这样部署时用环境变量定「出厂值」，运行期在「系统设置」页改的值落到库里。

数据全部由本平台自带采集写入本地 SQLite，**没有任何外部巡检平台配置**。
"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent        # backend/app
BACKEND_DIR = APP_DIR.parent                     # backend
PROJECT_DIR = BACKEND_DIR.parent                 # 项目根
FRONTEND_DIR = PROJECT_DIR / "frontend"

# 内置默认值（出厂口径）
DEFAULTS = {
    "cache_ttl": "20",
    "period_days": "7",
    "site_name": "林鉴知微平台 | LinScopePlatform",
    "org_name": "林鉴知微技术服务股份有限公司 · 网络运维中心",
}


def _load_dotenv() -> None:
    """把 backend/.env（或 config.env）里的键值读进环境变量（不覆盖已有值）。"""
    for name in (".env", "config.env"):
        path = BACKEND_DIR / name
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


_load_dotenv()


def env(name: str, default: str = "") -> str:
    value = (os.environ.get(name) or "").strip()
    return value or default


DATA_DIR = Path(env("NIP_DATA_DIR") or str(BACKEND_DIR / "data"))
DB_PATH = DATA_DIR / "netinspect.sqlite3"


def default_settings() -> dict:
    """出厂设置（环境变量优先于内置默认值）。"""
    return {
        "cache_ttl": env("CACHE_TTL", DEFAULTS["cache_ttl"]),
        "period_days": env("PERIOD_DAYS", DEFAULTS["period_days"]),
        "site_name": env("SITE_NAME", DEFAULTS["site_name"]),
        "org_name": env("ORG_NAME", DEFAULTS["org_name"]),
    }
