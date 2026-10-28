# -*- coding: utf-8 -*-
"""FastAPI 应用：接口 + 前端静态站点（一个进程同时提供 API 与页面）。

启动：`python run.py`（等价 `uvicorn app.main:app`）。前端仍是纯静态站点，
直接 `file://` 打开也能跑，只是需要把 API 地址指到本服务（见 frontend 里的设置）。
"""
from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import backup, config, service
from . import auth
from .collect import scheduler
from .routers import auth as auth_router
from .routers import collect as collect_router
from .routers import platform, remote as remote_router, reports, system
from .store import get_store

app = FastAPI(title="林鉴知微平台 | LinScopePlatform API",
              description="网络设备健康巡检平台后端（纯本地 SSH 采集）",
              version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Export-Id", "X-Export-Rows",
                    "X-Export-Devices", "X-Export-Tables", "X-Export-Images",
                    "X-Export-Source"],
)

app.include_router(auth_router.router)            # 登录 / 退出 / 账号与会话（公开 + 鉴权混合）
app.include_router(system.router)
app.include_router(platform.router)
app.include_router(reports.router)
app.include_router(remote_router.router)          # 远程登录（含 WebSocket 控制台）
app.include_router(collect_router.router)         # 自带采集（华为 VRP）
app.include_router(collect_router.devices_router)  # 设备台账（本平台维护）


# 不需要登录的路径：登录页探活、健康检查、接口文档、前端静态资源
PUBLIC_PATHS = ("/api/auth/status", "/api/auth/login", "/api/system/health", "/api/system/build", "/api/system/branding",
                "/docs", "/openapi.json", "/redoc")
# 只有管理员能碰的写接口（其余写接口 operator 及以上）
ADMIN_PATHS = ("/api/system/settings", "/api/auth/users",
               "/api/auth/events", "/api/remote/policy")
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def _is_public(path: str, method: str) -> bool:
    """前端静态资源永远公开（登录页也得能加载）；API 只放行白名单。"""
    if not path.startswith("/api"):
        return True
    if method == "POST" and path == "/api/auth/logout":
        return False
    for prefix in PUBLIC_PATHS:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else ""


def _required_write_permission(path: str) -> str | None:
    """返回写接口所需权限；None 表示登录用户自助接口。"""
    if path == "/api/auth/password" or path == "/api/auth/logout" \
            or path.startswith("/api/auth/sessions/"):
        return None
    if path.startswith("/api/auth/users"):
        return "users"
    if path.startswith("/api/system/settings") or path.startswith("/api/system/backup"):
        return "settings"
    if path.startswith("/api/remote/policy") or path.startswith("/api/remote/host-key"):
        return "settings"
    if path.startswith("/api/collect/settings") or path.startswith("/api/collect/purge"):
        return "settings"
    if path.startswith("/api/remote/"):
        return "remote"
    if path.startswith("/api/devices") or path.startswith("/api/ledger/import"):
        return "ledger_write"
    if path.startswith("/api/collect/run") or path.startswith("/api/collect/precheck"):
        return "sync"
    if path.startswith("/api/reports/archive/"):
        return "sync"
    # 默认拒绝只读用户写操作：以后新增写接口也默认需要运维工程师及以上。
    return "sync"


@app.middleware("http")
async def require_login(request: Request, call_next):
    """全站鉴权：公开路径放行，其余必须带有效令牌；写操作按角色分级。"""
    path = request.url.path
    request.state.user = None
    request.state.token = ""
    if _is_public(path, request.method):
        return await call_next(request)

    token = ""
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    if not token:
        token = (request.headers.get("x-auth-token") or "").strip()
    if not token:
        token = (request.query_params.get("token") or "").strip()
    user = auth.resolve(token) if token else None
    if not user:
        # WebSocket 自己处理（这里只管 HTTP）
        return JSONResponse(status_code=401, content={
            "error": "未登录或会话已过期", "code": "unauthorized"})
    request.state.user = user
    request.state.token = token

    if request.method not in SAFE_METHODS:
        perms = auth.permissions_of(user)
        required = _required_write_permission(path)
        if required and not perms.get(required):
            auth.log_event(
                user.get("username") or "", "permission_denied",
                "%s %s；缺少权限 %s" % (request.method, path, required),
                ip=_client_ip(request), operator=user.get("username") or "",
                target_type="api", result="denied")
            return JSONResponse(status_code=403, content={
                "error": "当前角色没有该操作权限", "code": "forbidden",
                "required_permission": required})

    response = await call_next(request)

    # 所有写操作至少留下一条真实操作者记录；业务动作另有更细的事件。
    if request.method not in SAFE_METHODS and path.startswith("/api") \
            and path != "/api/auth/login":
        actor = user.get("username") or "unknown"
        auth.log_event(
            actor, "api_write", "%s %s -> %s" % (request.method, path, response.status_code),
            ip=_client_ip(request), operator=actor, target_type="api",
            result="success" if response.status_code < 400 else "failed")
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy",
                                "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "connect-src 'self' ws: wss:; font-src 'self' data:; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; "
        "frame-ancestors 'self'")
    return response


@app.middleware("http")
async def no_stale_assets(request: Request, call_next):
    """前端静态资源每次都回源校验（no-cache = 可缓存但必须 revalidate）。

    内网平台常常是「就地更新」：改了 JS 不换文件名。若不加这条，浏览器会按
    Last-Modified 做启发式缓存，用户看到的还是旧页面（改完代码像没生效）。
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers.setdefault("Cache-Control", "no-cache, must-revalidate")
    return response


@app.middleware("http")
async def add_timing(request: Request, call_next):
    started = time.time()
    response = await call_next(request)
    response.headers["X-Elapsed-Ms"] = str(int((time.time() - started) * 1000))
    return response


@app.on_event("startup")
def _startup():
    get_store().init()
    service.settings()
    created = auth.bootstrap_admin()          # 首次启动建一个管理员（口令见日志/文件）
    from tools import test_device_lab
    test_device_lab.start()
    scheduler.start()                         # 定时采集（可在「系统设置 → 采集」里关掉）
    backup.start_scheduler()                  # 平台数据自动备份（默认 24 小时）
    if created:
        print("[auth] 已创建初始管理员 %s / %s（%s）"
              % (created["username"], created["password"],
                 "随机生成，见 data/initial_admin_password.txt" if created["generated"]
                 else "来自环境变量 NIP_ADMIN_PASSWORD"))


@app.on_event("shutdown")
def _shutdown_test_lab():
    from tools import test_device_lab
    test_device_lab.stop()


@app.get("/api")
def api_root():
    values = get_store().get_settings()
    return {
        "name": values.get("site_name") or "林鉴知微平台 | LinScopePlatform",
        "version": "1.3.0",
        "data_flow": "设备（SSH 只读） → 本平台自带采集 → 本地 SQLite → 页面 / Excel / Word / PDF",
        "endpoints": [
            "GET  /api/system/status", "GET  /api/system/meta",
            "POST /api/system/settings",
            "GET  /api/dashboard/overview?days=7",
            "GET  /api/dashboard/resources?days=7",
            "GET  /api/devices?keyword=&type=&status=&page=&page_size=",
            "GET  /api/devices/{id|ip}", "PUT  /api/devices/{id|ip}/ledger",
                        "GET  /api/health/server?device=", "GET  /api/health/switch?device=",
            "GET  /api/health/security?device=",
            "GET  /api/alerts?hours=&severity=&status=",
            "GET  /api/inspections?hours=&kind=", "GET  /api/backups",
            "GET  /api/reports/templates", "GET  /api/reports/archive",
            "GET  /api/collect/overview", "POST /api/collect/run",
            "GET  /api/collect/runs", "GET  /api/collect/logs",
            "POST /api/devices", "PUT  /api/devices/{ip}", "POST /api/devices/import",
            "GET  /api/remote/overview", "GET  /api/remote/credentials",
            "PUT  /api/remote/credentials/{ip}", "POST /api/remote/test",
            "WS   /api/remote/session/{ip}?mode=full", "GET  /api/remote/sessions",
            "GET  /api/remote/policy", "POST /api/remote/policy",
            "GET  /api/remote/sftp/list", "GET  /api/remote/sftp/download",
            "POST /api/remote/sftp/upload", "POST /api/remote/sftp/mkdir",
            "POST /api/remote/sftp/rename", "DELETE /api/remote/sftp/item",
            "GET  /api/reports/export?kind=&format=xlsx|csv",
            "GET  /api/reports/export/{id}", "DELETE /api/reports/archive/{id}",
            "GET  /docs",
        ],
    }


# 前端静态站点挂在最后：/api 与 /docs 优先，其余路径交给 frontend/ 目录
if config.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True),
              name="frontend")




