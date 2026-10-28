# -*- coding: utf-8 -*-
"""启动入口：python run.py [--host 0.0.0.0] [--port 1314] [--reload]

默认启用自签名 HTTPS。证书首次启动生成在数据目录 tls/ 下，随 Docker 数据卷迁移。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config            # noqa: E402
from app.store import get_store   # noqa: E402
from app.tls import ensure_self_signed  # noqa: E402


def _tls_enabled() -> bool:
    value = (os.environ.get("NIP_TLS_ENABLED", "1") or "1").strip().lower()
    return value not in ("0", "false", "no", "off", "disabled")


def main() -> None:
    parser = argparse.ArgumentParser(description="林鉴知微平台 | LinScopePlatform 后端")
    parser.add_argument("--host", default=os.environ.get("NIP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("NIP_PORT", "1314")))
    parser.add_argument("--reload", action="store_true", help="改代码自动重载（开发用）")
    parser.add_argument("--tls-cert", default=os.environ.get("NIP_TLS_CERT", ""))
    parser.add_argument("--tls-key", default=os.environ.get("NIP_TLS_KEY", ""))
    args = parser.parse_args()

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    get_store().init()

    ssl_certfile = ssl_keyfile = None
    scheme = "http"
    if _tls_enabled():
        cert_path = args.tls_cert or str(config.DATA_DIR / "tls" / "server.crt")
        key_path = args.tls_key or str(config.DATA_DIR / "tls" / "server.key")
        hosts = os.environ.get("NIP_TLS_HOSTS", "localhost,127.0.0.1,server,localhost")
        info = ensure_self_signed(cert_path, key_path, hosts)
        ssl_certfile, ssl_keyfile = info["cert"], info["key"]
        scheme = "https"

    import uvicorn
    print("林鉴知微平台 | LinScopePlatform")
    print("  接口文档 : %s://%s:%d/docs" % (scheme, args.host, args.port))
    print("  可视化台 : %s://%s:%d/" % (scheme, args.host, args.port))
    print("  数据目录 : %s" % config.DATA_DIR)
    if scheme == "https":
        print("  TLS 证书 : %s" % ssl_certfile)
        print("  自签名证书首次访问会出现浏览器安全提示，可选择“高级 -> 继续访问”。")
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload,
                ssl_certfile=ssl_certfile, ssl_keyfile=ssl_keyfile)


if __name__ == "__main__":
    main()
